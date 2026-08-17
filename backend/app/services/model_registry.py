"""Model registry + champion/challenger retraining.

Champion/challenger lifecycle:
  1. retrain_challenger() trains a fresh XGBoost bundle per combo from the
     candle archive (same features/labels as the bundled models) and saves it
     under ml_model/challengers/ with a versioned name.
  2. validate_challenger() replays the SAME recent window through both the
     current champion (or bundled fallback) and the challenger using the
     backtest engine, comparing out-of-sample performance.
  3. promote() marks the winner champion; older versions stay as candidates
     for rollback.

The live DecisionService consults the registry for each combo at load time;
when no champion is registered it uses the bundled static models.
"""

import logging
import os
import pickle
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from xgboost import XGBClassifier

from app import models

LOGGER = logging.getLogger('dolphin')

DOLPHIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dolphin')
MODEL_DIR = os.path.join(DOLPHIN_DIR, 'common', 'ml_model')
CHALLENGE_DIR = os.path.join(MODEL_DIR, 'challengers')

MIN_VALIDATION_TRADES = 15     # backtest sample needed to trust a comparison


def combo_str(bar_sec: int, expiry_sec: int) -> str:
    return f'{bar_sec}_{expiry_sec}'


def parse_combo(key: str) -> tuple[int, int]:
    b, e = key.split('_')
    return int(b), int(e)


def bundle_path(combo: str, version: int) -> str:
    return os.path.join(CHALLENGE_DIR, f'{combo}_v{version}.sav')


# ---------------------------------------------------------------------------
# registry queries
# ---------------------------------------------------------------------------

async def list_models(session: AsyncSession, combo: str | None = None) -> list[dict]:
    q = select(models.ModelVersion).order_by(models.ModelVersion.combo,
                                             models.ModelVersion.version)
    if combo:
        q = q.where(models.ModelVersion.combo == combo)
    rows = list((await session.execute(q)).scalars().all())
    return [{'id': r.id, 'combo': r.combo, 'version': r.version, 'status': r.status,
             'model_path': r.model_path, 'metrics': r.metrics or {},
             'created_at': str(r.created_at)} for r in rows]


async def champion_for(session: AsyncSession, combo: str) -> models.ModelVersion | None:
    q = select(models.ModelVersion).where(
        models.ModelVersion.combo == combo,
        models.ModelVersion.status == 'champion')
    return (await session.execute(q)).scalars().first()


async def _next_version(session: AsyncSession, combo: str) -> int:
    cur = (await session.execute(
        select(func.max(models.ModelVersion.version)).where(
            models.ModelVersion.combo == combo))).scalar() or 0
    return int(cur) + 1


async def register(session: AsyncSession, combo: str, path: str,
                   metrics: dict) -> models.ModelVersion:
    version = await _next_version(session, combo)
    row = models.ModelVersion(combo=combo, version=version, model_path=path,
                              status='candidate', metrics=metrics or {},
                              created_at=datetime.now(timezone.utc))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def promote(session: AsyncSession, combo: str, version: int | None = None,
                  model_id: int | None = None) -> dict:
    """Promote a candidate to champion (demotes the previous champion)."""
    if model_id is not None:
        q = select(models.ModelVersion).where(models.ModelVersion.id == model_id)
    else:
        q = select(models.ModelVersion).where(models.ModelVersion.combo == combo,
                                              models.ModelVersion.version == version)
    target = (await session.execute(q)).scalars().first()
    if target is None:
        return {'ok': False, 'msg': 'model not found'}
    await session.execute(
        models.ModelVersion.__table__.update()
        .where(models.ModelVersion.combo == combo)
        .values(status='candidate'))
    target.status = 'champion'
    await session.commit()
    LOGGER.info(f'promoted {combo} v{target.version} to champion')
    return {'ok': True, 'combo': combo, 'version': target.version}


async def rollback(session: AsyncSession, combo: str, version: int) -> dict:
    return await promote(session, combo, version=version)


# ---------------------------------------------------------------------------
# training + validation
# ---------------------------------------------------------------------------

class _BundleML:
    """Backtest-engine-compatible view over a single trained bundle."""

    def __init__(self, combo, bundle, theta=0.65):
        self.combo_models = {combo: bundle}
        self.theta = theta

    def compute_features(self, candles, bar_sec):
        from dolphin.ml_service import DecisionService
        svc = object.__new__(DecisionService)     # no init cost
        return DecisionService.compute_features(svc, candles, bar_sec)


def train_bundle(candles, bar_sec: int, expiry_sec: int) -> dict:
    """Train a fresh bundle from a candles DataFrame (archive format) and
    return {bundle, metrics} without saving."""
    import sys as _sys
    if DOLPHIN_DIR not in _sys.path:
        _sys.path.insert(0, DOLPHIN_DIR)
    from dolphin.multi_tf_models import (MQL_COMBOS, XGB_DEFAULTS,
                                         build_dataset, walk_forward)

    use_mql = (bar_sec, expiry_sec) in MQL_COMBOS
    raw = candles.copy()
    raw['datetime'] = pd.to_datetime(raw['datetime'])
    if raw['datetime'].dt.tz is not None:
        raw['datetime'] = raw['datetime'].dt.tz_convert('UTC').dt.tz_localize(None)
    if bar_sec > 300:
        out = []
        for sym, grp in raw.groupby('symbol'):
            g = grp.set_index('datetime').resample(f'{bar_sec}s').agg(
                open=('open', 'first'), high=('high', 'max'),
                low=('low', 'min'), close=('close', 'last'),
                volume=('volume', 'sum')).dropna().reset_index()
            g['symbol'] = sym
            out.append(g)
        raw = pd.concat(out, ignore_index=True).sort_values(
            ['symbol', 'datetime']).reset_index(drop=True)
    meta, feats = build_dataset(raw, bar_sec, expiry_sec, use_mql=use_mql)
    drop_cols = [c for c in feats.columns if not c.startswith('mql_')]
    full = meta.join(feats).dropna(subset=drop_cols)
    if use_mql:
        for c in feats.columns:
            if c.startswith('mql_'):
                full[c] = full[c].fillna(0.0)
    meta = full[['datetime', 'symbol', 'atr', 'entry', 'exit', 'fwd', 'label']]
    feats = full[feats.columns]
    if len(full) < 200:
        raise ValueError(f'not enough rows to train ({len(full)} < 200)')

    X_tr, y_tr, X_te, y_te, m_te = walk_forward(feats, meta)
    model = XGBClassifier(**XGB_DEFAULTS)
    model.fit(X_tr, y_tr)
    P = model.predict_proba(X_te)
    best = np.maximum(P[:, 1], P[:, 2])
    actual = np.where(m_te['fwd'].values > 0, 1,
                      np.where(m_te['fwd'].values < 0, 2, 0))
    pred = np.where(P[:, 1] >= P[:, 2], 1, 2)
    wins = (pred == actual) & (actual != 0)
    th = 0.55
    m = best >= th
    n = int(m.sum())
    train_acc = float(np.mean((model.predict(X_tr) == y_tr.values)))
    metrics = {
        'rows': len(full), 'test_rows': len(X_te),
        'train_acc': round(train_acc, 4),
        'val_trades': n,
        'val_win_rate': round(float(wins[m].mean()), 4) if n else None,
        'trained_at': str(datetime.now(timezone.utc)),
    }
    bundle = {'model': model, 'features': list(feats.columns),
              'columns': list(feats.columns),
              'bar_sec': bar_sec, 'expiry_sec': expiry_sec}
    return bundle, metrics


def save_bundle(bundle: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(bundle, f)
    return path


def load_bundle(path: str) -> dict:
    with open(path, 'rb') as f:
        bundle = pickle.load(f)
    bundle['columns'] = list(bundle['features'])
    return bundle


async def validate_challenger(session: AsyncSession, combo: tuple[int, int],
                              challenger_bundle: dict,
                              window_days: int = 7) -> dict:
    """Replay the recent `window_days` of archive candles through both the
    current production model and the challenger, comparing out-of-sample
    metrics. Returns {'champion': {...}, 'challenger': {...}, 'verdict'}."""
    import asyncio
    from app.services import persistence
    from app.backtest.engine import run_backtest_sync

    bar_sec, expiry_sec = combo
    key = combo_str(*combo)
    candles = await persistence.load_candles(session)
    if candles.empty:
        return {'verdict': 'no-data', 'msg': 'archive empty'}
    start = None
    if window_days:
        from datetime import timedelta
        start = datetime.now(timezone.utc) - timedelta(days=window_days)
        candles = candles[candles['datetime'] >= start]

    # champion: registry champion if present, else the bundled static model
    champion_bundle = None
    champ = await champion_for(session, key)
    if champ is not None:
        try:
            champion_bundle = load_bundle(champ.model_path)
        except Exception as e:
            LOGGER.warning(f'champion bundle load failed ({champ.model_path}): {e}')
    if champion_bundle is None:
        from dolphin.ml_service import COMBO_MODELS, MODEL_DIR as STATIC_DIR
        fname = COMBO_MODELS.get(combo)
        if not fname:
            return {'verdict': 'no-model', 'msg': f'no model for {key}'}
        champion_bundle = load_bundle(os.path.join(STATIC_DIR, fname))

    def _run(bundle):
        ml = _BundleML(combo, bundle, theta=0.65)
        return run_backtest_sync(ml, candles, combos=[combo],
                                 order_types=['binary'], theta=0.55,
                                 cooldown_min=0, max_trades_per_day=1000,
                                 max_daily_loss_pct=100.0)

    champ_res = await asyncio.to_thread(_run, champion_bundle)
    chal_res = await asyncio.to_thread(_run, challenger_bundle)
    c, k = champ_res['summary'], chal_res['summary']

    def pick(s):
        return {'trades': s.get('settled', 0), 'win_rate': s.get('win_rate'),
                'profit_factor': s.get('profit_factor'),
                'net_pnl': s.get('net_pnl'), 'expectancy': s.get('expectancy')}

    verdict = 'insufficient'
    if c['settled'] >= MIN_VALIDATION_TRADES and k['settled'] >= MIN_VALIDATION_TRADES:
        # compare expectancy; champion holds unless challenger clearly better
        chal = k['expectancy'] or 0.0
        champ_e = c['expectancy'] or 0.0
        if chal > champ_e * 1.1 + 0.001:
            verdict = 'promote'
        else:
            verdict = 'keep'
    return {'verdict': verdict, 'champion': pick(c), 'challenger': pick(k),
            'window_days': window_days}


async def retrain_challenger(session: AsyncSession, combo: tuple[int, int],
                             window_days: int = 7, auto_promote: bool = True) -> dict:
    """Full champion/challenger cycle for one combo."""
    import asyncio
    from app.services import persistence
    from app.backtest import engine as bt_engine

    bar_sec, expiry_sec = combo
    key = combo_str(*combo)
    candles = await persistence.load_candles(session)
    if candles.empty:
        return {'ok': False, 'combo': key, 'msg': 'archive empty'}
    try:
        bundle, metrics = await asyncio.to_thread(
            train_bundle, candles, bar_sec, expiry_sec)
    except Exception as e:
        return {'ok': False, 'combo': key, 'msg': f'train failed: {e}'}

    validation = await validate_challenger(session, combo, bundle,
                                           window_days=window_days)
    path = bundle_path(key, await _next_version(session, key))
    save_bundle(bundle, path)
    row = await register(session, key, path, {
        **metrics, 'validation': validation})

    result = {'ok': True, 'combo': key, 'version': row.version,
              'metrics': metrics, 'validation': validation}
    if auto_promote and validation.get('verdict') == 'promote':
        await promote(session, key, model_id=row.id)
        result['promoted'] = True
    return result