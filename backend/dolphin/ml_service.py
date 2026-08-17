"""Production ML decision service - multi-timeframe (Phase 3).

Turns broker candles (o/h/l/c/v/t) for the watchlist into per-combo trade
decisions. A combo is (bar_sec, expiry_sec):

    candles (5m native) -> resample to bar_sec -> light features (25)
                         -> raw XGB per combo -> P(call)/P(put)
    gate: max-prob >= theta AND calendar veto passes

Light feature set (multi_tf_models.build_light_features): ~60-bar warmup,
bar-scale agnostic - every combo is usable from the olymp WS window.

Combos with measured keep-or-kill results (multi_tf_models.py):
  (300,900)  5m -> 15m  60.5% @0.55     (300,1800) 5m -> 30m  60.9% @0.55
  (300,3600) 5m -> 1h   55.9% @0.55     (900,3600) 15m -> 1h 75.6% @0.55
  (1800,3600) 30m -> 1h 67.3% @0.55     (+ dead combos kept for completeness)
"""

import logging
import os
import pickle
import sys

import numpy as np
import pandas as pd
import ta

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from multi_tf_models import build_light_features
from features.mql_signals import add_mql_features
from common.calendar_features import EconomicCalendar

LOGGER = logging.getLogger('dolphin')

MODEL_DIR = os.path.join(CURR, 'common', 'ml_model')

THETA = 0.65            # probability gate (window mode uses 0.55-0.60)
PAYOUT = 0.90
SLIPPAGE_TAX = 0.02
STAKE_PCT = 0.01

# mql features need ~60+ bars (zigzag depth 30 + confirmation); the (300,3600)
# bundle is trained on the light set + mql set (see mql_eval.py promote)
LIGHT_WARMUP_BARS = 80
# all 8 trained combos: more candidate evaluations per hour feeds the
# hourly-guarantee picker (900/900, 900/1800, 1800/1800 add breadth)
DEFAULT_COMBOS = [(300, 900), (300, 1800), (300, 3600),
                  (900, 900), (900, 1800), (900, 3600),
                  (1800, 1800), (1800, 3600)]

COMBO_MODELS = {
    (300, 900): 'combo_300_900_boot.sav',
    (300, 1800): 'combo_300_1800_boot.sav',
    (300, 3600): 'combo_300_3600_boot.sav',
    (900, 900): 'combo_900_900_boot.sav',
    (900, 1800): 'combo_900_1800_boot.sav',
    (900, 3600): 'combo_900_3600_boot.sav',
    (1800, 1800): 'combo_1800_1800_boot.sav',
    (1800, 3600): 'combo_1800_3600_boot.sav',
}


def normalize_symbols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['symbol'] = df['symbol'].str.replace('_OTC', '', regex=False)
    df['symbol'] = np.where(df['symbol'].str.startswith('FX:'), df['symbol'], 'FX:' + df['symbol'])
    return df


def resample_bars(raw: pd.DataFrame, bar_sec: int) -> pd.DataFrame:
    """Resample the 5m native feed to a higher bar scale (per symbol)."""
    if bar_sec == 300:
        return raw
    out = []
    for sym, grp in raw.groupby('symbol'):
        g = grp.set_index('datetime').resample(f'{bar_sec}s').agg(
            open=('open', 'first'), high=('high', 'max'),
            low=('low', 'min'), close=('close', 'last'),
            volume=('volume', 'sum')).dropna().reset_index()
        g['symbol'] = sym
        out.append(g)
    df = pd.concat(out, ignore_index=True)
    # drop the still-forming top bar: its bin end exceeds the newest completed 5m bar
    latest_5m = raw['datetime'].max()
    df = df[df['datetime'] + pd.Timedelta(seconds=bar_sec) <= latest_5m]
    return df.sort_values(['symbol', 'datetime']).reset_index(drop=True)


class DecisionService:
    def __init__(self, theta=THETA, payout=PAYOUT):
        self.theta = theta
        self.payout = payout
        self.combo_models = {}
        for combo, fname in COMBO_MODELS.items():
            path = os.path.join(MODEL_DIR, fname)
            if os.path.exists(path):
                self.combo_models[combo] = self._load(path)
        LOGGER.info(f'loaded {len(self.combo_models)} combo models')
        self.calendar = EconomicCalendar()
        self.calendar.refresh()

    @staticmethod
    def _load(path):
        with open(path, 'rb') as f:
            bundle = pickle.load(f)
        bundle['columns'] = list(bundle['features'])
        return bundle

    # -- normalization (shared) ---------------------------------------------

    def _normalize(self, candles: pd.DataFrame) -> pd.DataFrame:
        raw = normalize_symbols(candles)
        if 'o' in raw.columns and 'open' not in raw.columns:
            raw = raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low',
                                      'c': 'close', 'v': 'volume'})
        if 'datetime' not in raw.columns and 't' in raw.columns:
            raw['datetime'] = pd.to_datetime(raw['t'], unit='s', utc=True)
        raw['datetime'] = pd.to_datetime(raw['datetime'])
        if raw['datetime'].dt.tz is not None:
            raw['datetime'] = raw['datetime'].dt.tz_localize(None)
        raw['datetime'] = raw['datetime'].astype('datetime64[us]')
        # completed candles only: drop the newest row per symbol when live
        if len(raw):
            feed_newest = raw['datetime'].max()
            now_utc = pd.Timestamp.utcnow().tz_localize(None)
            if abs((now_utc - feed_newest).total_seconds()) < 24 * 3600:
                newest_per_symbol = raw.groupby('symbol')['datetime'].transform('max')
                raw = raw[raw['datetime'] < newest_per_symbol]
        raw = raw.drop_duplicates(subset=['datetime', 'symbol']).sort_values(
            ['symbol', 'datetime']).reset_index(drop=True)
        if 'volume' not in raw.columns:
            raw['volume'] = np.nan
        return raw

    # -- feature computation (light set, bar-scale agnostic) ----------------

    def compute_features(self, candles: pd.DataFrame, bar_sec: int = 300):
        raw = self._normalize(candles)
        raw = resample_bars(raw, bar_sec)
        feats = build_light_features(raw)
        mql = add_mql_features(raw)
        feats = pd.concat([feats, mql.loc[feats.index]], axis=1)
        feats['symbol'] = raw['symbol'].values
        feats['datetime'] = raw['datetime'].values
        atr = ta.volatility.average_true_range(raw['high'], raw['low'], raw['close'], window=14)
        meta = raw[['symbol', 'datetime', 'open', 'high', 'low', 'close']].copy()
        meta['atr14'] = atr.values
        return feats, meta

    # -- decision -----------------------------------------------------------

    def decide_for_combo(self, candles, bar_sec, expiry_sec, equity=1000.0, now=None,
                         theta=None):
        bundle = self.combo_models.get((bar_sec, expiry_sec))
        if bundle is None:
            return []
        gate = theta if theta is not None else self.theta
        feats, meta = self.compute_features(candles, bar_sec)
        per_symbol = feats.groupby('symbol', sort=False)
        meta_by_symbol = meta.set_index('symbol')
        veto, evt = self.calendar.veto(now)

        decisions = []
        for symbol, grp in per_symbol:
            if len(grp) < LIGHT_WARMUP_BARS:
                continue
            row = grp.iloc[-1]
            X = pd.DataFrame([row[bundle['columns']].values], columns=bundle['columns'])
            X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
            if X.isna().any(axis=1).iloc[0]:
                continue
            P = bundle['model'].predict_proba(X)[0]
            p_call, p_put = float(P[1]), float(P[2])
            best = max(p_call, p_put)
            direction = 'CALL' if p_call >= p_put else 'PUT'
            ev = best * (self.payout - SLIPPAGE_TAX) - (1 - best)
            trade = best >= gate and not veto and ev > 0.0

            mrow = meta_by_symbol.loc[symbol].iloc[-1]
            entry = float(mrow['close'])
            sign = 1.0 if direction == 'CALL' else -1.0
            atr = float(mrow['atr14']) if not np.isnan(mrow['atr14']) else 0.0
            decisions.append({
                'symbol': symbol,
                'tf': f'{bar_sec // 60}m',
                'candle_close': str(mrow['datetime']),
                'candle_open': round(float(mrow['open']), 5),
                'candle_high': round(float(mrow['high']), 5),
                'candle_low': round(float(mrow['low']), 5),
                'candle_close_price': round(entry, 5),
                'atr': round(atr, 5),
                'entry_price': round(entry, 5),
                'target_price': round(entry + sign * atr, 5) if atr else round(entry, 5),
                'stop_loss': round(entry - sign * 0.5 * atr, 5) if atr else round(entry, 5),
                'action': direction if trade else 'NEUTRAL',
                'expiry': f'{expiry_sec // 60}m',
                'p_call': round(p_call, 4),
                'p_put': round(p_put, 4),
                'best_prob': round(best, 4),
                'ev_score': round(ev, 4),
                'stake': round(equity * STAKE_PCT, 2) if trade else 0.0,
                'news_veto': bool(veto),
                'news_next': (evt or {}).get('title') if veto else None,
                'model': f'combo_{bar_sec}_{expiry_sec}',
                'rationale': (f'P={best:.2f} {direction} at gate {self.theta}; '
                              f'EV={ev:+.3f}') if trade else 'below gate',
            })
        return decisions

    def decide_all(self, candles, combos=None, equity=1000.0, now=None, theta=None):
        """Decide for every combo. Returns list of decision dicts.

        theta overrides the gate (used by the hourly-guarantee scan, which
        evaluates candidates down to the fallback floor).
        """
        combos = combos or DEFAULT_COMBOS
        out = []
        for bar_sec, expiry_sec in combos:
            out += self.decide_for_combo(candles, bar_sec, expiry_sec, equity=equity,
                                         now=now, theta=theta)
        return out
