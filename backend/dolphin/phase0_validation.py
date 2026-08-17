"""Phase 0 validation harness: can a >70% per-trade win ratio be engineered?

Method (all leakage rules enforced):
- Features: lookback-only (bars <= i), computed from the broker-style candles.
- Labels: certainty-based. Tradeable only when |forward move| >= 1.0 * ATR(14).
  Entry = open of next candle, expiry = `expiry_sec` later.
- Walk-forward: fit XGB on train (60%), isotonic-calibrate on validate (15%),
  evaluate ONLY on untouched test (last 25%) per asset.
- Threshold sweep reports calibrated-P gated rows: win rate (binary win =
  direction at expiry, the real broker condition), strong-move precision,
  trade frequency, and EV at 90% payout.

Run:  python phase0_validation.py [15m|5m|30m|1h]
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
from xgboost import XGBClassifier

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from TradingStradegy.mt4stradegies import binary_arrows, super_arrows, super_signals, super_signals_v3, tm_indicator

OUT = os.path.join(CURR, 'common', 'MachineLearningModel', 'output')

# ---------------------------------------------------------------------------
# signal modules (ported from v1, lookback-only) -> confluence features
# ---------------------------------------------------------------------------

def signal_chain(data: pd.DataFrame, use_super_arrow: bool = True) -> pd.DataFrame:
    superv3 = super_signals_v3.SuperV3SignalPredictor(data.copy()).run()
    superv2 = super_signals.SuperSignalV2Generator(superv3.reset_index(drop=True)).run()
    binary = binary_arrows.BinaryArrowSignalPredictor(superv2.reset_index(drop=True)).run()
    if use_super_arrow:
        superarrow = super_arrows.SuperArrowSignalGenerator(binary.reset_index(drop=True)).run()
        result = tm_indicator.TMIndicator(superarrow.reset_index(drop=True)).run()
    else:
        result = tm_indicator.TMIndicator(binary.reset_index(drop=True)).run()
    return result.reset_index(drop=True)

# ---------------------------------------------------------------------------
# feature builder (lookback-only)
# ---------------------------------------------------------------------------

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    v = df['volume'] if 'volume' in df.columns and df['volume'].notna().any() else pd.Series(1.0, index=df.index)

    atr = ta.volatility.average_true_range(h, l, c, window=14)
    atr_safe = atr.replace(0, np.nan)

    rsi = ta.momentum.rsi(c, window=14)
    ema9 = ta.trend.ema_indicator(c, window=9)
    ema21 = ta.trend.ema_indicator(c, window=21)
    ema50 = ta.trend.ema_indicator(c, window=50)
    macd_line = ta.trend.macd(c, window_slow=26, window_fast=12)
    macd_sig = ta.trend.macd_signal(c, window_slow=26, window_fast=12)
    macd_hist = macd_line - macd_sig

    day = df['datetime'].dt.date
    # group by symbol AND day so VWAP is per symbol per session
    vwap_group = [df['symbol'], day] if 'symbol' in df.columns else day
    tp = (h + l + c) / 3.0
    cum_pv = (tp * v).groupby(vwap_group).cumsum()
    cum_v = v.groupby(vwap_group).cumsum()
    vwap = cum_pv / cum_v.replace(0, np.nan)

    sw_hi = h.rolling(20).max()
    sw_lo = l.rolling(20).min()

    bb_mid = c.rolling(10).mean()
    bb_std = c.rolling(10).std()
    bb_width = (bb_mid + 2 * bb_std - (bb_mid - 2 * bb_std)) / bb_mid
    bb_width_pctile = bb_width.rolling(250).rank(pct=True)

    f = pd.DataFrame(index=df.index)
    f['dist_swing_hi_atr'] = (sw_hi - c) / atr_safe
    f['dist_swing_lo_atr'] = (c - sw_lo) / atr_safe
    f['dist_vwap_atr'] = (c - vwap) / atr_safe
    f['rsi14'] = rsi
    f['rsi_slope'] = rsi - rsi.shift(3)
    f['macd_hist_mom'] = (macd_hist - macd_hist.shift(1)) / atr_safe
    f['ema_ratio'] = ema9 / ema21 - 1.0
    f['ema_cross'] = (ema9 > ema21).astype(int).diff().clip(-1, 1)
    f['ht_slope'] = (ema50 - ema50.shift(12)) / atr_safe
    f['bb_width_pctile'] = bb_width_pctile
    f['body_ratio'] = (c - o).abs() / (h - l).replace(0, np.nan)
    f['range_3_atr'] = (h - l).rolling(3).mean() / atr_safe
    f['vol_zscore'] = (v - v.rolling(20).mean()) / v.rolling(20).std().replace(0, np.nan)
    f['atr_pctile'] = atr.rolling(250).rank(pct=True)

    hour = df['datetime'].dt.hour + df['datetime'].dt.minute / 60.0
    is_london = ((hour >= 8) & (hour < 16)) & df['datetime'].dt.weekday < 5
    is_ny = ((hour >= 13) & (hour < 21)) & (df['datetime'].dt.weekday < 5)
    f['session_code'] = np.where(is_ny & is_london, 3, np.where(is_ny, 2, np.where(is_london, 1, 0)))
    f['session_elapsed'] = np.where(is_london | is_ny, (hour - np.where(hour >= 13, 13, 8)) / 8.0, 0.0)
    f['friday_late'] = ((df['datetime'].dt.weekday == 4) & (hour >= 15)).astype(int)
    return f

# ---------------------------------------------------------------------------
# certainty labels
# ---------------------------------------------------------------------------

def build_labels(df: pd.DataFrame, expiry_sec: int, bar_sec: int, atr, strong_atr_scale=0.5) -> pd.Series:
    k = expiry_sec // bar_sec                       # bars from entry open to expiry
    entry = df['open'].shift(-1)                    # trade opens next candle
    exit_close = df['close'].shift(-k)              # expires k bars later
    fwd = exit_close - entry
    strong = fwd.abs() >= strong_atr_scale * atr
    label = pd.Series(0, index=df.index)
    label[strong & (fwd > 0)] = 1                   # STRONG CALL
    label[strong & (fwd < 0)] = 2                   # STRONG PUT
    return label

# ---------------------------------------------------------------------------
# dataset loader (dedupe, sort, features, labels, forward path for win checks)
# ---------------------------------------------------------------------------

def load_dataset(files, expiry_sec, bar_sec, use_super_arrow=True):
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
    data = data.drop_duplicates(subset=['datetime', 'symbol']).sort_values(['symbol', 'datetime']).reset_index(drop=True)

    atr = ta.volatility.average_true_range(data['high'], data['low'], data['close'], window=14)
    sig = signal_chain(data, use_super_arrow=use_super_arrow)
    signals = sig[['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow', 'TMSignal'] + (['SuperArrowSignal'] if use_super_arrow else [])]
    data['confluence_call'] = (signals == 1).sum(axis=1)
    data['confluence_put'] = (signals == 2).sum(axis=1)

    feats = build_features(data)
    feats['confluence_call'] = data['confluence_call']
    feats['confluence_put'] = data['confluence_put']
    labels = build_labels(data, expiry_sec, bar_sec, atr)

    entry = data['open'].shift(-1)
    k = expiry_sec // bar_sec
    exit_close = data['close'].shift(-k)
    fwd = exit_close - entry

    out = pd.DataFrame({
        'datetime': data['datetime'], 'symbol': data['symbol'],
        'atr': atr.values, 'entry': entry.values, 'exit': exit_close.values,
        'fwd': fwd.values, 'label': labels.values,
    })
    return out, feats
# ---------------------------------------------------------------------------
# walk-forward evaluation
# ---------------------------------------------------------------------------

def walk_forward_holdout(feats, meta, model_fn, train_frac=0.60, val_frac=0.15):
    """Per-asset temporal split. Returns (X_test, y_test, meta_test, cal_model).

    Calibration: XGB fit on train; per-class isotonic calibration fitted on
    the untouched validation window (equivalent to cv='prefit' which sklearn
    dropped).
    """
    X_tr, y_tr, X_va, y_va, X_te, y_te, meta_te = [], [], [], [], [], [], []
    for symbol, grp in meta.groupby('symbol', sort=False):
        X = feats.loc[grp.index]
        n = len(grp)
        i_tr, i_va = int(n * train_frac), int(n * (train_frac + val_frac))
        X_tr.append(X.iloc[:i_tr]); y_tr.append(grp['label'].iloc[:i_tr])
        X_va.append(X.iloc[i_tr:i_va]); y_va.append(grp['label'].iloc[i_tr:i_va])
        X_te.append(X.iloc[i_va:]); y_te.append(grp['label'].iloc[i_va:])
        meta_te.append(grp.iloc[i_va:])
    X_tr = pd.concat(X_tr); y_tr = pd.concat(y_tr)
    X_va = pd.concat(X_va); y_va = pd.concat(y_va)
    X_te = pd.concat(X_te); y_te = pd.concat(y_te)
    meta_te = pd.concat(meta_te)

    base = model_fn()
    base.fit(X_tr, y_tr)
    return X_te, y_te, meta_te, _Calibrator(base, X_va, y_va), base


class _Calibrator:
    """Per-class isotonic calibration on the validation window."""

    def __init__(self, base, X_va, y_va):
        from sklearn.isotonic import IsotonicRegression
        self.base = base
        p = base.predict_proba(X_va)
        self.regs = [IsotonicRegression(out_of_bounds='clip') for _ in range(p.shape[1])]
        for k, reg in enumerate(self.regs):
            reg.fit(p[:, k], (y_va == k).astype(int).values)

    def predict_proba(self, X):
        p = self.base.predict_proba(X).astype(float)
        for k, reg in enumerate(self.regs):
            p[:, k] = reg.predict(p[:, k])
        s = p.sum(axis=1, keepdims=True)
        return p / np.where(s > 0, s, 1.0)


def wilson_ci(n, phat, z=1.96):
    if n == 0:
        return 0.0, 0.0
    d = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / d
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / d
    return center - half, center + half


def evaluate(X_te, y_te, meta_te, cal, payout=0.90, atr_scale=1.0, raw=None):
    P = cal.predict_proba(X_te)
    if raw is not None:
        P_raw = raw.predict_proba(X_te)
    p_call, p_put = P[:, 1], P[:, 2]
    best = np.maximum(p_call, p_put)
    pred_dir = np.where(p_call >= p_put, 1, 2)
    actual_dir = np.where(meta_te['fwd'] > 0, 1, np.where(meta_te['fwd'] < 0, 2, 0))
    win = (pred_dir == actual_dir) & (actual_dir != 0)
    strong_hit = win & (meta_te['fwd'].abs() >= atr_scale * meta_te['atr'])
    n_days = meta_te.groupby(['symbol', meta_te['datetime'].dt.date]).ngroups

    def table(best_probs, tag):
        rows = []
        for th in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
            m = best_probs >= th
            n = int(m.sum())
            if n == 0:
                rows.append((th, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0))
                continue
            w = float(win[m].mean())
            s = float(strong_hit[m].mean())
            lo, hi = wilson_ci(n, w)
            ev = w * (payout - 0.02) - (1 - w)
            rows.append((th, n, w * 100, lo * 100, hi * 100, s * 100, ev, n / n_days))
        print(f'  -- {tag} --')
        print(f'  {"theta":>6} {"trades":>8} {"win%":>7} {"CIlo":>6} {"CIhi":>6} {"strong%":>8} {"EV@90":>7} {"tr/day":>7}')
        for th, n, w, lo, hi, s, ev, tpd in rows:
            print(f'  {th:>6.2f} {n:>8} {w:>7.2f} {lo:>6.1f} {hi:>6.1f} {s:>8.2f} {ev:>7.3f} {tpd:>7.2f}')

    table(best, 'calibrated')
    if raw is not None:
        table(np.maximum(P_raw[:, 1], P_raw[:, 2]), 'raw-xgb')


def run_pipeline(label, files, expiry_sec, bar_sec, use_super_arrow=True):
    print(f'\n{"="*78}\n{label}\n  files={len(files)}  expiry={expiry_sec}s  bar={bar_sec}s')
    meta, feats = load_dataset(files, expiry_sec, bar_sec, use_super_arrow=use_super_arrow)

    full = meta.join(feats)
    full = full.dropna(subset=[c for c in feats.columns] + ['atr', 'fwd', 'entry', 'exit'])
    feats = full[feats.columns]
    meta = full[['datetime', 'symbol', 'atr', 'entry', 'exit', 'fwd', 'label']]

    n_strong = (meta['label'] != 0).sum()
    print(f'  rows={len(meta):,}  strong rows={n_strong:,} ({n_strong/len(meta)*100:.1f}%)  '
          f'span={meta.datetime.min()} -> {meta.datetime.max()}')

    X_te, y_te, meta_te, cal, base = walk_forward_holdout(feats, meta, lambda: XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.05, min_child_weight=4,
        subsample=0.8, colsample_bytree=0.8, eval_metric='mlogloss', n_jobs=-1))

    print(f'  TEST (untouched): rows={len(X_te):,}  symbols={meta_te.symbol.nunique()}  '
          f'span={meta_te.datetime.min()} -> {meta_te.datetime.max()}')
    evaluate(X_te, y_te, meta_te, cal, raw=base)
    return X_te, y_te, meta_te, cal


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else '15m'

    if which == '15m':
        files = [f for f in glob.glob(os.path.join(OUT, 'fifteen_mins', '*.csv'))]
        run_pipeline('15m expiry on 15-min candles (multi-asset)', files, 900, 900)
    elif which == '5m':
        files = [f for f in glob.glob(os.path.join(OUT, 'five_mins', '*_5_Min*.csv'))]
        run_pipeline('15m expiry on 5-min candles (multi-asset)', files, 900, 300)
    elif which == '30m':
        files = glob.glob(os.path.join(CURR, 'Data', 'EURUSD_30_MIN.csv'))
        run_pipeline('30m expiry on 30-min candles (EURUSD)', files, 1800, 1800)
        run_pipeline('1h expiry on 30-min candles (EURUSD)', files, 3600, 1800)


if __name__ == '__main__':
    main()
