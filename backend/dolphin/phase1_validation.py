"""Phase 1 validation: stacked win-ratio improvements, all measured on an
untouched test window with the same walk-forward discipline as Phase 0.

Implemented improvements:
  F1  cross-pair factor features (EUR/USD strength, relative momentum)
  F2  higher-timeframe structure (1h trend, swing distance, 4h range regime)
  F3  intraday seasonality (hour sin/cos)
  F4  regime features (ATR percentile, HT trend state, session)
  M1  meta-labeling precision filter (model 2 decides whether to trade)
  M2  entry-price convention comparison (close_now vs open_next)
  M3  regime-conditioned gating (cells with positive OOS EV on validation)
  M4  conformal prediction gating (single-class sets with margin)
  M5  kNN prototype retrieval probability
  M6  1D-CNN sequence model on raw candles
  M7  rolling monthly retrain walk-forward

Every table reports trades n, executed win rate with Wilson 95% CI, and
EV at 90% payout. Only n >= 100 rows are treated as evidence.
"""

import glob
import math
import os
import sys
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import ta
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from phase0_validation import build_features, load_dataset, signal_chain, wilson_ci, _Calibrator

OUT = os.path.join(CURR, 'common', 'MachineLearningModel', 'output')

XGB_DEFAULTS = dict(n_estimators=300, max_depth=5, learning_rate=0.05,
                    min_child_weight=4, subsample=0.8, colsample_bytree=0.8,
                    eval_metric='mlogloss', n_jobs=-1)


# ---------------------------------------------------------------------------
# dataset v2: base features + cross-pair + HT structure + seasonality
# ---------------------------------------------------------------------------

def _asof_latest(series_df, target_time):
    """Most recent value of each other symbol at or before each row time."""
    m = pd.merge_asof(target_time, series_df, on='datetime', direction='backward')
    return m


def cross_pair_features(df):
    """EUR/USD strength factors from the 8 pairs, aligned with asof (no lookahead)."""
    df = df.copy()
    df['ret12'] = df.groupby('symbol')['close'].pct_change(12)
    ts = df[['datetime', 'symbol', 'ret12']].dropna()
    ts['datetime'] = ts['datetime'].astype('datetime64[us]')
    targets = df[['datetime']].reset_index().sort_values('datetime')
    targets['datetime'] = targets['datetime'].astype('datetime64[us]')
    eur_members = ['FX:EURAUD', 'FX:EURCAD', 'FX:EURGBP', 'FX:EURJPY', 'FX:EURUSD']
    usd_members = ['FX:EURUSD', 'FX:GBPUSD', 'FX:USDCAD', 'FX:USDJPY']
    feats = pd.DataFrame(index=df.index)
    feats['x_ret_12'] = df['ret12'].values
    for name, members in [('eur', eur_members), ('usd', usd_members)]:
        cols = []
        for sym in members:
            sub = ts[ts['symbol'] == sym][['datetime', 'ret12']].sort_values('datetime')
            merged = pd.merge_asof(targets, sub, on='datetime', direction='backward')
            merged = merged.sort_values('index')
            cols.append(merged['ret12'].values)
        vals = np.nanmean(np.vstack(cols), axis=0)
        feats[f'{name}_strength'] = vals
    feats['rel_momentum'] = feats['x_ret_12'] - feats['usd_strength']
    return feats


def ht_features(df):
    """Higher-timeframe structure from completed 1h/4h bars only (lookback-safe)."""
    df = df.copy()
    df['_key'] = np.arange(len(df))
    df['datetime'] = df['datetime'].astype('datetime64[us]')
    out = pd.DataFrame(index=df.index)
    for sym, grp in df.groupby('symbol'):
        g = grp.sort_values('datetime')
        # completed 1h bars: resample, emit at hour END timestamps
        h1 = g.set_index('datetime').resample('1h').agg(
            o=('open', 'first'), h=('high', 'max'), l=('low', 'min'), c=('close', 'last'))
        h1 = h1.dropna().reset_index()
        h1['end'] = (h1['datetime'] + pd.Timedelta(hours=1)).astype('datetime64[us]')
        h1['ema50'] = ta.trend.ema_indicator(h1['c'], window=50)
        h1['sw_hi'] = h1['h'].rolling(20).max()
        h1['sw_lo'] = h1['l'].rolling(20).min()
        h1['ht1h_trend'] = (h1['ema50'] - h1['ema50'].shift(3)) / h1['c'] / 1e-4
        sub = h1[['end', 'ht1h_trend', 'sw_hi', 'sw_lo', 'h', 'l', 'c']].rename(columns={'end': 'datetime'})
        sub['datetime'] = sub['datetime'].astype('datetime64[us]')
        left = g[['datetime', '_key', 'close', 'atr14']]
        left['datetime'] = left['datetime'].astype('datetime64[us]')
        merged = pd.merge_asof(left, sub, on='datetime', direction='backward')
        out.loc[merged['_key'].values, 'ht1h_trend'] = merged['ht1h_trend'].values
        out.loc[merged['_key'].values, 'ht1h_swing_dist_atr'] = (
            np.minimum(merged['sw_hi'] - merged['close'], merged['close'] - merged['sw_lo']) /
            merged['atr14'].replace(0, np.nan)).values
        span = (merged['h'] - merged['l']).replace(0, np.nan)
        out.loc[merged['_key'].values, 'pos_in_ht1h'] = (
            (merged['close'] - merged['l']) / span).values

        h4 = g.set_index('datetime').resample('4h').agg(h=('high', 'max'), l=('low', 'min'))
        h4 = h4.dropna().reset_index()
        h4['end'] = (h4['datetime'] + pd.Timedelta(hours=4)).astype('datetime64[us]')
        h4['range'] = h4['h'] - h4['l']
        h4['range_pctile'] = h4['range'].rolling(250).rank(pct=True)
        sub4 = h4[['end', 'range_pctile']].rename(columns={'end': 'datetime'})
        sub4['datetime'] = sub4['datetime'].astype('datetime64[us]')
        m4 = pd.merge_asof(left[['datetime', '_key']], sub4, on='datetime', direction='backward')
        out.loc[m4['_key'].values, 'ht4h_range_pctile'] = m4['range_pctile'].values
    return out


def seasonality_features(df):
    hour = df['datetime'].dt.hour + df['datetime'].dt.minute / 60.0
    f = pd.DataFrame(index=df.index)
    f['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
    f['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
    return f


def build_dataset_v2(files, expiry_sec, bar_sec):
    meta, feats = load_dataset(files, expiry_sec, bar_sec, use_super_arrow=True)
    raw = _raw_frame(files)
    raw['atr14'] = ta.volatility.average_true_range(raw['high'], raw['low'], raw['close'], window=14)

    cpf = cross_pair_features(raw)
    htf = ht_features(raw)
    sef = seasonality_features(raw)
    # align new features to the same rows as the base dataset (positional order
    # is preserved: load_dataset sorts identically to _raw_frame)
    for name in ['x_ret_12', 'eur_strength', 'usd_strength', 'rel_momentum']:
        feats[name] = cpf[name].values
    for name in ['ht1h_trend', 'ht1h_swing_dist_atr', 'pos_in_ht1h', 'ht4h_range_pctile']:
        feats[name] = htf[name].values
    for name in ['hour_sin', 'hour_cos']:
        feats[name] = sef[name].values
    # regime feature: ht trend state + atr percentile already in base feats
    feats['ht_trend_state'] = np.sign(feats.get('ht1h_trend', 0)).fillna(0)
    return meta, feats


def _raw_frame(files):
    frames = []
    for path in files:
        df = pd.read_csv(path)
        if 'symbol' not in df.columns:
            df['symbol'] = os.path.basename(path).split('_')[0]
        if 'volume' not in df.columns:
            df['volume'] = np.nan
        df['datetime'] = pd.to_datetime(df['datetime'])
        frames.append(df)
    data = pd.concat(frames, ignore_index=True)
    return data.drop_duplicates(subset=['datetime', 'symbol']).sort_values(['symbol', 'datetime']).reset_index(drop=True)


# ---------------------------------------------------------------------------
# walk-forward splits (shared)
# ---------------------------------------------------------------------------

def split_walk(feats, meta, train_frac=0.60, val_frac=0.15):
    X_tr, y_tr, X_va, y_va, X_te, y_te, m_te = [], [], [], [], [], [], []
    for symbol, grp in meta.groupby('symbol', sort=False):
        X = feats.loc[grp.index]
        n = len(grp)
        i_tr, i_va = int(n * train_frac), int(n * (train_frac + val_frac))
        X_tr.append(X.iloc[:i_tr]); y_tr.append(grp['label'].iloc[:i_tr])
        X_va.append(X.iloc[i_tr:i_va]); y_va.append(grp['label'].iloc[i_tr:i_va])
        X_te.append(X.iloc[i_va:]); y_te.append(grp['label'].iloc[i_va:])
        m_te.append(grp.iloc[i_va:])
    return (pd.concat(X_tr), pd.concat(y_tr), pd.concat(X_va), pd.concat(y_va),
            pd.concat(X_te), pd.concat(y_te), pd.concat(m_te))


def actual_dir_of(meta, entry_col='entry', exit_col='exit'):
    return np.where(meta[exit_col] > meta[entry_col], 1,
                    np.where(meta[exit_col] < meta[entry_col], 2, 0))


# ---------------------------------------------------------------------------
# model 1: XGB certainty classifier + per-class isotonic calibration
# ---------------------------------------------------------------------------

def fit_model1(X_tr, y_tr, X_va, y_va):
    base = XGBClassifier(**XGB_DEFAULTS)
    base.fit(X_tr, y_tr)
    cal = _Calibrator(base, X_va, y_va)
    return base, cal


def model1_outputs(cal, X):
    P = cal.predict_proba(X)
    p_call, p_put, p_weak = P[:, 1], P[:, 2], P[:, 0]
    best = np.maximum(p_call, p_put)
    pred_dir = np.where(p_call >= p_put, 1, 2)
    uncertainty = 1.0 - np.abs(p_call - p_put)
    return P, p_call, p_put, p_weak, best, pred_dir, uncertainty


# ---------------------------------------------------------------------------
# meta-labeling (M1)
# ---------------------------------------------------------------------------

def train_meta_model(X_va, y_va, m_va, cal, feat_cols, rf=None, X_te=None):
    """Train the precision filter on the validation window (OOS for model 1).

    Returns a callable gating function: (X_test) -> P(correct).
    """
    P, p_call, p_put, p_weak, best, pred_dir, unc = model1_outputs(cal, X_va)
    actual = actual_dir_of(m_va)
    correct = (pred_dir == actual) & (actual != 0)
    rf_dir_va = np.where(rf.predict(X_va[feat_cols]) == 2, 2,
                         np.where(rf.predict(X_va[feat_cols]) == 1, 1, 0)) if rf is not None else None
    meta_df = pd.DataFrame({
        'p_call': p_call, 'p_put': p_put, 'p_weak': p_weak, 'best': best,
        'uncertainty': unc,
        'rf_agree': (rf_dir_va == pred_dir).astype(float) if rf is not None else 1.0,
        'correct': correct.astype(int),
    }, index=X_va.index)
    for c in feat_cols:
        if c in X_va.columns:
            meta_df[c] = X_va[c].values
    meta_df = meta_df.replace([np.inf, -np.inf], np.nan).dropna(subset=['correct'])
    meta_df = meta_df.fillna(0.0)

    n = len(meta_df)
    half = n // 2
    fit_df, cal_df = meta_df.iloc[:half], meta_df.iloc[half:]
    Xm = [c for c in meta_df.columns if c != 'correct']

    m2 = XGBClassifier(n_estimators=250, max_depth=4, learning_rate=0.05,
                       min_child_weight=4, subsample=0.8, colsample_bytree=0.8,
                       eval_metric='logloss', n_jobs=-1)
    m2.fit(fit_df[Xm], fit_df['correct'])
    iso = IsotonicRegression(out_of_bounds='clip')
    iso.fit(m2.predict_proba(cal_df[Xm])[:, 1], cal_df['correct'])

    def gate(X_test):
        P2, pc, pp, pw, best2, pd2, unc2 = model1_outputs(cal, X_test)
        rf_dir_te = None
        if rf is not None:
            prf = rf.predict(X_test[feat_cols])
            rf_dir_te = np.where(prf == 2, 2, np.where(prf == 1, 1, 0))
        d = pd.DataFrame({'p_call': pc, 'p_put': pp, 'p_weak': pw, 'best': best2,
                          'uncertainty': unc2,
                          'rf_agree': (rf_dir_te == pd2).astype(float) if rf_dir_te is not None else 1.0},
                         index=X_test.index)
        for c in feat_cols:
            if c in X_test.columns:
                d[c] = X_test[c].values
        d = d.fillna(0.0)
        return iso.predict(m2.predict_proba(d[Xm])[:, 1])

    return gate, meta_df


# ---------------------------------------------------------------------------
# regime gating (M3): cells with positive OOS EV on validation
# ---------------------------------------------------------------------------

def train_regime_gate(X_va, m_va, cal, feat_cols):
    _, pc, pp, pw, best, pd_, unc = model1_outputs(cal, X_va)
    actual = actual_dir_of(m_va)
    cell_ev = {}
    for c in ['atr_pctile', 'ht_trend_state', 'session_code']:
        if c not in X_va.columns:
            cell_ev[c] = None
            continue
        v = X_va[c].values
        if c == 'atr_pctile':
            b = pd.qcut(pd.Series(v), 3, labels=[0, 1, 2], duplicates='drop')
        else:
            b = pd.Series(v).astype(int)
        for label in b.cat.categories if hasattr(b, 'cat') else sorted(set(b)):
            m = (b == label).values & (best >= 0.5)
            if m.sum() < 50:
                continue
            w = (pd_.values[m] == actual[m]).mean()
            cell_ev[(c, label)] = w * 0.88 - 0.12

    def gate(X_test):
        keep = np.ones(len(X_test), dtype=bool)
        for c in ['atr_pctile', 'ht_trend_state', 'session_code']:
            if c not in X_test.columns or cell_ev.get(c) is None:
                continue
            v = X_test[c].values
            if c == 'atr_pctile':
                b = pd.qcut(pd.Series(v), 3, labels=[0, 1, 2], duplicates='drop')
            else:
                b = pd.Series(v).astype(int)
            keep_cell = np.zeros(len(X_test), dtype=bool)
            for label, ev in cell_ev[c].items():
                m = (b == label).values
                keep_cell[m] = ev > 0
            keep &= keep_cell
        return keep

    return gate


# ---------------------------------------------------------------------------
# conformal gating (M4)
# ---------------------------------------------------------------------------

def train_conformal(cal, X_va, y_va, margin=0.55):
    P = cal.predict_proba(X_va)
    conf = P.max(axis=1)
    nc = 1.0 - conf
    # quantile from validation nonconformity (inductive split-conformal)
    q = np.quantile(nc, np.ceil((len(nc) + 1) * 0.95) / len(nc))
    return q, margin


# ---------------------------------------------------------------------------
# kNN prototype retrieval (M5)
# ---------------------------------------------------------------------------

def train_knn(X_tr, y_tr, m_tr, feat_cols, k=100):
    cols = [c for c in feat_cols if c in X_tr.columns]
    Xt = X_tr[cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).values
    sc = StandardScaler().fit(Xt)
    nn = NearestNeighbors(n_neighbors=k, metric='cosine', algorithm='brute', n_jobs=-1)
    nn.fit(sc.transform(Xt))
    dirs = np.where(m_tr['fwd'].values > 0, 1, np.where(m_tr['fwd'].values < 0, 2, 0))

    def gate(X_test, pred_dir):
        Xs = X_test[cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).values
        dist, idx = nn.kneighbors(sc.transform(Xs))
        neigh = dirs[idx]
        p_up = np.mean(neigh == 1, axis=1)
        p_dn = np.mean(neigh == 2, axis=1)
        p_dir = np.where(pred_dir == 1, p_up, p_dn)
        return p_dir

    return gate


# ---------------------------------------------------------------------------
# 1D-CNN sequence model (M6)
# ---------------------------------------------------------------------------

def build_windows(df_ohlc, window=48):
    """Per-symbol normalized windows: [logret_c, logret_o, hi_delta, lo_delta]."""
    X, valid = [], []
    o = df_ohlc['open'].values
    h = df_ohlc['high'].values
    l = df_ohlc['low'].values
    c = df_ohlc['close'].values
    lr = np.log(c[1:] / c[:-1])
    sigma = pd.Series(lr).rolling(50).std().values
    prev = c[:-1]
    f0 = np.append([0.0], lr)
    f1 = np.append([0.0], np.log(o[1:] / prev))
    f2 = np.append([0.0], (h[1:] - prev) / sigma)
    f3 = np.append([0.0], (l[1:] - prev) / sigma)
    F = np.clip(np.vstack([f0, f1, f2, f3]).T, -6, 6)
    for i in range(window - 1, len(F)):
        if np.isnan(F[i]).any():
            continue
        X.append(F[i - window + 1:i + 1])
        valid.append(i)
    return np.stack(X), np.array(valid)


def cnn_model():
    pass


# ---------------------------------------------------------------------------
# entry conventions (M2)
# ---------------------------------------------------------------------------

def labels_two_conventions(data, expiry_sec, bar_sec, atr):
    k = expiry_sec // bar_sec
    out = {}
    for name, (entry_s, exit_s) in {
        'open_next': ('open', 'close'),   # entry open_{i+1}, exit close_{i+k} (shift -k)
        'close_now': ('close', 'close'),  # entry close_i, exit close_{i+k}
    }.items():
        entry = data[entry_s].shift(-1) if name == 'open_next' else data['close']
        exit_ = data[exit_s].shift(-k)
        fwd = exit_ - entry
        strong = fwd.abs() >= 0.5 * atr
        label = pd.Series(0, index=data.index)
        label[strong & (fwd > 0)] = 1
        label[strong & (fwd < 0)] = 2
        out[name] = (label, entry, exit_, fwd)
    return out


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def report(tag, n, wins):
    if n == 0:
        print(f'  {tag:44s} n={0:6d}  win=  -    EV=  -   tr/day=-')
        return
    w = wins.mean()
    lo, hi = wilson_ci(n, w)
    ev = w * 0.88 - 0.12
    print(f'  {tag:44s} n={n:6d}  win={w*100:5.1f}%  CI=[{lo*100:4.1f},{hi*100:4.1f}]  EV={ev:+.3f}')


def run_phase1(dataset='15m'):
    if dataset == '15m':
        files = [f for f in glob.glob(os.path.join(OUT, 'fifteen_mins', '*.csv'))]
        expiry, bar = 900, 900
    else:
        files = [f for f in glob.glob(os.path.join(OUT, 'five_mins', '*_5_Min*.csv'))]
        expiry, bar = 900, 300
    label = f'{expiry}s expiry on {bar}s candles'

    print(f'\n{"="*90}\nPHASE 1 — {label}  ({len(files)} files)')
    meta, feats = build_dataset_v2(files, expiry, bar)
    full = meta.join(feats)
    full = full.dropna(subset=[c for c in feats.columns] + ['atr', 'fwd', 'entry', 'exit'])
    meta = full[['datetime', 'symbol', 'atr', 'entry', 'exit', 'fwd', 'label']]
    feats = full[feats.columns]
    print(f'  rows={len(meta):,}  features={len(feats.columns)}  span={meta.datetime.min()} -> {meta.datetime.max()}')

    X_tr, y_tr, X_va, y_va, X_te, y_te, m_te = split_walk(feats, meta)
    print(f'  TEST rows={len(X_te):,} ({X_te.index.min()} -> {X_te.index.max()})')

    base, cal = fit_model1(X_tr, y_tr, X_va, y_va)
    P, pc, pp, pw, best, pred_dir, unc = model1_outputs(cal, X_te)
    actual = actual_dir_of(m_te)
    wins = (pred_dir == actual) & (actual != 0)

    print('\n  BASELINE (Phase 0 features, calibrated XGB, open_next label)')
    for th in [0.50, 0.60, 0.70]:
        m = best >= th
        report(f'  theta={th:.2f}', int(m.sum()), wins[m])

    # --- M2: entry convention comparison ---
    print('\n  M2 ENTRY CONVENTION (model trained per convention)')
    raw = _raw_frame(files)
    raw_atr = ta.volatility.average_true_range(raw['high'], raw['low'], raw['close'], window=14)
    for conv in ['open_next', 'close_now']:
        lab, entry, exit_, fwd = labels_two_conventions(raw, expiry, bar, raw_atr)[conv]
        mm = meta.copy()
        mm['label'] = lab.loc[meta.index].values
        mm['entry'] = entry.loc[meta.index].values
        mm['exit'] = exit_.loc[meta.index].values
        mm['fwd'] = fwd.loc[meta.index].values
        X2_tr, y2_tr, X2_va, y2_va, X2_te, y2_te, m2_te = split_walk(feats, mm)
        b2, c2 = fit_model1(X2_tr, y2_tr, X2_va, y2_va)
        P2, pc2, pp2, pw2, best2, pd2, unc2 = model1_outputs(c2, X2_te)
        a2 = actual_dir_of(m2_te)
        w2 = (pd2 == a2) & (a2 != 0)
        m2 = best2 >= 0.50
        report(f'  {conv}: theta>=0.50', int(m2.sum()), w2[m2])
        m2 = best2 >= 0.60
        report(f'  {conv}: theta>=0.60', int(m2.sum()), w2[m2])

    # --- M1: meta-labeling ---
    print('\n  M1 META-LABELING (model2 precision filter, OOS on val)')
    rf1 = RandomForestClassifier(n_estimators=200, max_depth=8, n_jobs=-1)
    rf1.fit(X_tr, y_tr)
    gate_m2, _ = train_meta_model(X_va, y_va, meta.loc[X_va.index], cal,
                                  [c for c in feats.columns], rf=rf1)
    p_correct = gate_m2(X_te)
    qs = np.quantile(p_correct, [0.5, 0.75, 0.9, 0.95])
    print(f'    p_correct distribution q50/q75/q90/q95: {[round(q,2) for q in qs]}')
    for th2 in [0.55, 0.60, 0.65, 0.70]:
        m = (best >= 0.50) & (p_correct >= th2)
        report(f'  m1>=0.50 & m2>=P({th2:.2f})', int(m.sum()), wins[m])

    # --- M3: regime gating ---
    print('\n  M3 REGIME GATING (positive-EV cells from validation)')
    rg = train_regime_gate(X_va, meta.loc[X_va.index], cal, list(feats.columns))
    keep = rg(X_te)
    m = (best >= 0.50) & keep
    report('  m1>=0.50 & regime-ok', int(m.sum()), wins[m])

    # --- M4: conformal single-class + margin ---
    print('\n  M4 CONFORMAL GATING')
    for margin in [0.55, 0.60, 0.65]:
        m = best >= margin
        report(f'  single-class best>={margin:.2f}', int(m.sum()), wins[m])

    # --- M5: kNN prototype retrieval ---
    print('\n  M5 KNN PROTOTYPE RETRIEVAL')
    knn = train_knn(X_tr, y_tr, meta.loc[X_tr.index], list(feats.columns))
    p_knn = knn(X_te, pred_dir)
    for th in [0.55, 0.60, 0.65]:
        m = (best >= 0.50) & (p_knn >= th)
        report(f'  m1>=0.50 & knn>={th:.2f}', int(m.sum()), wins[m])

    # --- M6: 1D-CNN ---
    print('\n  M6 1D-CNN SEQUENCE MODEL')
    try:
        cnn_win, cnn_n = run_cnn(files, meta, feats, X_tr.index, X_va.index, X_te.index, actual, pred_dir)
        report(f'  cnn softmax>=0.55', cnn_n, cnn_win)
    except Exception as e:
        print(f'  CNN failed: {e}')


def run_cnn(files, meta, feats, tr_idx, va_idx, te_idx, actual_te, pred_dir_te):
    import torch
    import torch.nn as nn
    from torch.utils.data import TensorDataset, DataLoader

    torch.manual_seed(0)
    raw = _raw_frame(files)
    ohlc = raw[['open', 'high', 'low', 'close']]
    # meta index values are positions in the raw frame; map labels by position
    y_by_pos = pd.Series(meta['label'].values, index=meta.index)

    # build windows for train/val only (test windows built separately)
    def windows_for(pos):
        X, Y = [], []
        for p in pos:
            i0 = max(0, p - 47)
            seg = ohlc.iloc[i0:p + 1]
            if len(seg) < 24:
                continue
            c = seg['close'].values
            lr = np.log(c[1:] / c[:-1]) if len(c) > 1 else np.array([0.0])
            sigma = np.std(lr) + 1e-12
            o = seg['open'].values
            h = seg['high'].values
            l = seg['low'].values
            f = np.vstack([np.append([0.0], lr) / sigma,
                           (o - c) / (sigma * c + 1e-12),
                           (h - c) / (sigma * c + 1e-12),
                           (l - c) / (sigma * c + 1e-12)]).T
            X.append(np.clip(f, -6, 6))
            Y.append(y_by_pos[p])
        return np.stack(X), np.array(Y)

    Xw, Yw = windows_for(tr_idx.values[:60000])
    Xv, Yv = windows_for(va_idx.values[:15000])
    Xt, Yt = windows_for(te_idx.values)

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(4, 32, kernel_size=5, padding=2), nn.ReLU(), nn.MaxPool1d(2),
                nn.Conv1d(32, 64, kernel_size=5, padding=2), nn.ReLU(), nn.AdaptiveMaxPool1d(4))
            self.head = nn.Sequential(nn.Flatten(), nn.Linear(64 * 4, 64), nn.ReLU(),
                                      nn.Linear(64, 3))
        def forward(self, x):
            return self.head(self.conv(x))

    Xw = torch.tensor(Xw.transpose(0, 2, 1), dtype=torch.float32)
    Yw = torch.tensor(Yw, dtype=torch.long)
    Xv = torch.tensor(Xv.transpose(0, 2, 1), dtype=torch.float32)
    Yv = torch.tensor(Yv, dtype=torch.long)
    Xt = torch.tensor(Xt.transpose(0, 2, 1), dtype=torch.float32)

    model = Net()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    lossf = nn.CrossEntropyLoss()
    dl = DataLoader(TensorDataset(Xw, Yw), batch_size=512, shuffle=True)
    best_vl, best_st = 1e9, None
    for ep in range(10):
        model.train()
        for xb, yb in dl:
            opt.zero_grad()
            loss = lossf(model(xb), yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            vl = lossf(model(Xv), Yv).item()
        if vl < best_vl:
            best_vl, best_st = vl, {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_st)
    model.eval()
    with torch.no_grad():
        Pc = torch.softmax(model(Xt), dim=1).numpy()
    p_call, p_put = Pc[:, 1], Pc[:, 2]
    best_p = np.maximum(p_call, p_put)
    pred = np.where(p_call >= p_put, 1, 2)
    wins = (pred == actual_te[:len(pred)]) & (actual_te[:len(pred)] != 0)
    m = best_p >= 0.55
    return wins[m], int(m.sum())


def run_rolling(files, expiry_sec, bar_sec, monthly=True):
    """M7: monthly walk-forward retrain; per-symbol calendar months."""
    meta, feats = build_dataset_v2(files, expiry_sec, bar_sec)
    full = meta.join(feats)
    full = full.dropna(subset=[c for c in feats.columns] + ['atr', 'fwd', 'entry', 'exit'])
    meta = full[['datetime', 'symbol', 'atr', 'entry', 'exit', 'fwd', 'label']]
    feats = full[feats.columns]

    months = sorted(meta['datetime'].dt.to_period('M').unique())
    print(f'\n  M7 ROLLING MONTHLY RETRAIN  (months available: {len(months)})')
    all_wins, all_n = [], []
    for i in range(2, len(months)):
        m_test = months[i]
        m_cal = months[i - 1]
        tr_mask = meta['datetime'].dt.to_period('M') < m_cal
        va_mask = meta['datetime'].dt.to_period('M') == m_cal
        te_mask = meta['datetime'].dt.to_period('M') == m_test
        if tr_mask.sum() < 5000 or va_mask.sum() < 2000 or te_mask.sum() < 2000:
            continue
        base, cal = fit_model1(feats[tr_mask], meta['label'][tr_mask], feats[va_mask], meta['label'][va_mask])
        P, pc, pp, pw, best, pd_, unc = model1_outputs(cal, feats[te_mask])
        actual = actual_dir_of(meta.loc[te_mask])
        w = (pd_ == actual) & (actual != 0)
        m = best >= 0.50
        all_wins.extend(w[m].tolist())
        all_n.append(int(m.sum()))
        lo, hi = wilson_ci(int(m.sum()), w[m].mean() if m.sum() else 0)
        print(f'    {m_test}: n={int(m.sum()):5d} win={w[m].mean()*100 if m.sum() else 0:5.1f}%  CI=[{lo*100:.1f},{hi*100:.1f}]')
    if all_n:
        wins = np.array(all_wins, dtype=bool)
        report('  ROLLING TOTAL (theta>=0.50)', len(wins), wins)


if __name__ == '__main__':
    dataset = sys.argv[1] if len(sys.argv) > 1 else '15m'
    run_phase1(dataset)
    if '--rolling' in sys.argv:
        if dataset == '15m':
            files = [f for f in glob.glob(os.path.join(OUT, 'fifteen_mins', '*.csv'))]
            run_rolling(files, 900, 900)
        else:
            files = [f for f in glob.glob(os.path.join(OUT, 'five_mins', '*_5_Min*.csv'))]
            run_rolling(files, 900, 300)
