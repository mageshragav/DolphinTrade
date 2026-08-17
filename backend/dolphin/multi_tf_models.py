"""Multi-timeframe model training: light-feature boot models per (bar, expiry).

Light features (bar-scale agnostic, ~50-bar warmup so every combo is usable
from the olymp WS window):
  base 17 with 50-bar percentile windows (no HT features - they need 42 days)
  + confluence 2 + cross-pair 4 + seasonality 2  = 25 features

Labels per combo: entry open_{i+1}, exit close_{i+k}, k = expiry/bar,
strong move >= 0.5 ATR.

Combos:
  5m bars  -> 15m (k=3), 30m (k=6), 1h (k=12)     [five_mins CSVs]
  15m bars -> 15m (k=1), 30m (k=2), 1h (k=4)      [fifteen_mins CSVs]
  30m bars -> 30m (k=1), 1h (k=2)                  [fifteen_mins resampled]

Run:  python multi_tf_models.py
"""

import glob
import os
import pickle
import sys
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import ta
from xgboost import XGBClassifier

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from phase1_validation import wilson_ci, XGB_DEFAULTS
from phase1_validation import cross_pair_features, seasonality_features
from features.mql_signals import add_mql_features

OUT = os.path.join(CURR, 'common', 'MachineLearningModel', 'output')
MODEL_DIR = os.path.join(CURR, 'common', 'ml_model')

PCT_WINDOW = 50          # percentile windows for the light boot set
THETAS = [0.50, 0.55, 0.60, 0.65]

# combos that use the MQL-derived feature set on top of the light set
# (validated by mql_eval.py: (300,3600) win@0.65 72.2% vs 66.9% baseline;
# every mql group additive; all other combos keep the light-only set)
MQL_COMBOS = {(300, 3600)}


def build_light_features(df):
    """Mirror of the base feature builder with ~50-bar warmup (no HT)."""
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    v = df['volume'] if 'volume' in df.columns and df['volume'].notna().any() else pd.Series(1.0, index=df.index)

    atr = ta.volatility.average_true_range(h, l, c, window=14)
    atr_safe = atr.replace(0, np.nan)

    rsi = ta.momentum.rsi(c, window=14)
    ema9 = ta.trend.ema_indicator(c, window=9)
    ema21 = ta.trend.ema_indicator(c, window=21)
    macd_line = ta.trend.macd(c, window_slow=26, window_fast=12)
    macd_sig = ta.trend.macd_signal(c, window_slow=26, window_fast=12)
    macd_hist = macd_line - macd_sig

    day = df['datetime'].dt.date
    grp = [df['symbol'], day] if 'symbol' in df.columns else day
    tp = (h + l + c) / 3.0
    cum_pv = (tp * v).groupby(grp).cumsum()
    cum_v = v.groupby(grp).cumsum()
    vwap = cum_pv / cum_v.replace(0, np.nan)

    sw_hi = h.rolling(20).max()
    sw_lo = l.rolling(20).min()

    bb_mid = c.rolling(10).mean()
    bb_std = c.rolling(10).std()
    bb_width = (bb_mid + 2 * bb_std - (bb_mid - 2 * bb_std)) / bb_mid

    f = pd.DataFrame(index=df.index)
    f['dist_swing_hi_atr'] = (sw_hi - c) / atr_safe
    f['dist_swing_lo_atr'] = (c - sw_lo) / atr_safe
    f['dist_vwap_atr'] = (c - vwap) / atr_safe
    f['rsi14'] = rsi
    f['rsi_slope'] = rsi - rsi.shift(3)
    f['macd_hist_mom'] = (macd_hist - macd_hist.shift(1)) / atr_safe
    f['ema_ratio'] = ema9 / ema21 - 1.0
    f['ema_cross'] = (ema9 > ema21).astype(int).diff().clip(-1, 1)
    f['bb_width_pctile'] = bb_width.rolling(PCT_WINDOW).rank(pct=True)
    f['body_ratio'] = (c - o).abs() / (h - l).replace(0, np.nan)
    f['range_3_atr'] = (h - l).rolling(3).mean() / atr_safe
    f['vol_zscore'] = (v - v.rolling(20).mean()) / v.rolling(20).std().replace(0, np.nan)
    f['atr_pctile'] = atr.rolling(PCT_WINDOW).rank(pct=True)

    hour = df['datetime'].dt.hour + df['datetime'].dt.minute / 60.0
    is_london = ((hour >= 8) & (hour < 16)) & (df['datetime'].dt.weekday < 5)
    is_ny = ((hour >= 13) & (hour < 21)) & (df['datetime'].dt.weekday < 5)
    f['session_code'] = np.where(is_ny & is_london, 3, np.where(is_ny, 2, np.where(is_london, 1, 0)))
    f['session_elapsed'] = np.where(is_london | is_ny, (hour - np.where(hour >= 13, 13, 8)) / 8.0, 0.0)
    f['friday_late'] = ((df['datetime'].dt.weekday == 4) & (hour >= 15)).astype(int)

    sef = seasonality_features(df)
    f['hour_sin'] = sef['hour_sin'].values
    f['hour_cos'] = sef['hour_cos'].values

    cpf = cross_pair_features(df)
    for c_ in ['x_ret_12', 'eur_strength', 'usd_strength', 'rel_momentum']:
        f[c_] = cpf[c_].values

    sig = signal_chain_light(df)
    f['confluence_call'] = (sig[['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow',
                                 'TMSignal', 'SuperArrowSignal']] == 1).sum(axis=1).values
    f['confluence_put'] = (sig[['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow',
                                'TMSignal', 'SuperArrowSignal']] == 2).sum(axis=1).values
    return f


def signal_chain_light(df):
    from TradingStradegy.mt4stradegies import (binary_arrows, super_arrows,
                                               super_signals, super_signals_v3, tm_indicator)
    superv3 = super_signals_v3.SuperV3SignalPredictor(df.copy()).run()
    superv2 = super_signals.SuperSignalV2Generator(superv3.reset_index(drop=True)).run()
    binary = binary_arrows.BinaryArrowSignalPredictor(superv2.reset_index(drop=True)).run()
    superarrow = super_arrows.SuperArrowSignalGenerator(binary.reset_index(drop=True)).run()
    result = tm_indicator.TMIndicator(superarrow.reset_index(drop=True)).run()
    return result.reset_index(drop=True)


def load_source(paths, bar_sec, from_bar_sec=None):
    """Load CSVs, resample to bar_sec when needed, return sorted raw frame."""
    frames = []
    for path in paths:
        df = pd.read_csv(path)
        if 'symbol' not in df.columns:
            df['symbol'] = os.path.basename(path).split('_')[0]
        if 'volume' not in df.columns:
            df['volume'] = np.nan
        df['datetime'] = pd.to_datetime(df['datetime'])
        frames.append(df)
    data = pd.concat(frames, ignore_index=True)
    data = data.drop_duplicates(subset=['datetime', 'symbol']).sort_values(
        ['symbol', 'datetime']).reset_index(drop=True)
    if from_bar_sec and bar_sec != from_bar_sec:
        out = []
        for sym, grp in data.groupby('symbol'):
            g = grp.set_index('datetime').resample(f'{bar_sec}s').agg(
                open=('open', 'first'), high=('high', 'max'),
                low=('low', 'min'), close=('close', 'last'),
                volume=('volume', 'sum')).dropna().reset_index()
            g['symbol'] = sym
            out.append(g)
        data = pd.concat(out, ignore_index=True).sort_values(
            ['symbol', 'datetime']).reset_index(drop=True)
    return data


def build_dataset(raw, bar_sec, expiry_sec, use_mql=False):
    """Light features (+ mql set when use_mql) + certainty labels."""
    k = expiry_sec // bar_sec
    atr = ta.volatility.average_true_range(raw['high'], raw['low'], raw['close'], window=14)
    feats = build_light_features(raw)
    if use_mql:
        mql = add_mql_features(raw)
        feats = pd.concat([feats, mql.loc[feats.index]], axis=1)

    entry = raw['open'].shift(-1)
    exit_close = raw['close'].shift(-k)
    fwd = exit_close - entry
    strong = fwd.abs() >= 0.5 * atr
    label = pd.Series(0, index=raw.index, dtype=float)
    label[strong & (fwd > 0)] = 1
    label[strong & (fwd < 0)] = 2

    meta = pd.DataFrame({
        'datetime': raw['datetime'], 'symbol': raw['symbol'],
        'atr': atr.values, 'entry': entry.values, 'exit': exit_close.values,
        'fwd': fwd.values, 'label': label.values,
    })
    return meta, feats


def walk_forward(feats, meta):
    X_tr, y_tr, X_te, y_te, m_te = [], [], [], [], []
    for symbol, grp in meta.groupby('symbol', sort=False):
        X = feats.loc[grp.index]
        n = len(grp)
        i_tr = int(n * 0.75)
        X_tr.append(X.iloc[:i_tr]); y_tr.append(grp['label'].iloc[:i_tr])
        X_te.append(X.iloc[i_tr:]); y_te.append(grp['label'].iloc[i_tr:])
        m_te.append(grp.iloc[i_tr:])
    return (pd.concat(X_tr), pd.concat(y_tr), pd.concat(X_te),
            pd.concat(y_te), pd.concat(m_te))


def train_combo(raw, bar_sec, expiry_sec, save=True):
    use_mql = (bar_sec, expiry_sec) in MQL_COMBOS
    meta, feats = build_dataset(raw, bar_sec, expiry_sec, use_mql=use_mql)
    drop_cols = [c for c in feats.columns if not c.startswith('mql_')] + ['atr', 'fwd']
    full = meta.join(feats).dropna(subset=drop_cols)
    if use_mql:
        for c in feats.columns:
            if c.startswith('mql_'):
                full[c] = full[c].fillna(0.0)
    meta = full[['datetime', 'symbol', 'atr', 'entry', 'exit', 'fwd', 'label']]
    feats = full[feats.columns]

    X_tr, y_tr, X_te, y_te, m_te = walk_forward(feats, meta)
    model = XGBClassifier(**XGB_DEFAULTS)
    model.fit(X_tr, y_tr)

    actual = np.where(m_te['fwd'].values > 0, 1, np.where(m_te['fwd'].values < 0, 2, 0))
    P = model.predict_proba(X_te)
    best = np.maximum(P[:, 1], P[:, 2])
    pred = np.where(P[:, 1] >= P[:, 2], 1, 2)
    wins = (pred == actual) & (actual != 0)
    hour = pd.to_datetime(m_te['datetime']).dt.hour.values
    days = m_te['datetime'].dt.date.nunique()

    print(f'  [{bar_sec}s -> {expiry_sec}s expiry] k={expiry_sec//bar_sec} '
          f'rows={len(meta):,} test={len(X_te):,} ({m_te.datetime.min()} -> {m_te.datetime.max()})'
          f'{" [mql features]" if use_mql else ""}')
    for th in THETAS:
        m = best >= th
        n = int(m.sum())
        if n == 0:
            continue
        w = wins[m].mean()
        lo, hi = wilson_ci(n, w)
        print(f'    theta={th:.2f}: n={n:6d} win={w*100:5.1f}% CI=[{lo*100:.1f},{hi*100:.1f}] '
              f'per-hour={n/(days*8):.2f}')
    m = (best >= 0.55) & (hour >= 15) & (hour < 17)
    if m.sum():
        print(f'    WINDOW 15-17 UTC @0.55: n={int(m.sum())} win={wins[m].mean()*100:.1f}%')

    if save:
        name = f'combo_{bar_sec}_{expiry_sec}_boot.sav'
        pickle.dump({'model': model, 'features': list(feats.columns),
                     'bar_sec': bar_sec, 'expiry_sec': expiry_sec},
                    open(os.path.join(MODEL_DIR, name), 'wb'))
        print(f'    saved {name}')
    return model


def main():
    five = [f for f in glob.glob(os.path.join(OUT, 'five_mins', '*_5_Min*.csv'))]
    fifteen = [f for f in glob.glob(os.path.join(OUT, 'fifteen_mins', '*.csv'))]

    raw5 = load_source(five, 300)
    raw15 = load_source(fifteen, 900)
    raw30 = load_source(fifteen, 1800, from_bar_sec=900)

    print('=' * 84)
    print('5m candles')
    for exp in [900, 1800, 3600]:
        print('-' * 60)
        train_combo(raw5, 300, exp)

    print('=' * 84)
    print('15m candles')
    for exp in [900, 1800, 3600]:
        print('-' * 60)
        train_combo(raw15, 900, exp)

    print('=' * 84)
    print('30m candles (resampled from 15m)')
    for exp in [1800, 3600]:
        print('-' * 60)
        train_combo(raw30, 1800, exp)

    print('=' * 84)
    print('DONE')


if __name__ == '__main__':
    main()
