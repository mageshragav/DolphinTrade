"""Phase-1 gate for the MQL-derived features (mt4indicators/later port).

Compare per combo: light-feature baseline vs light + mql_* features,
walk-forward (75/25 per symbol), theta sweep + the 15-17 UTC window readout.

Only promote features into production bundles if they BEAT the baseline
(win-rate and signal count at theta) — run the ablation pass to confirm
each feature group is additive.

EVAL VERDICT (Aug 2026, Mar-Jul 2024 data, fair fillna comparison):
  (300, 3600) 5m->1h  : PROMOTE full mql set. win@0.65 = 72.2% vs 66.9%
                        baseline (+5.2pp); 15-17 window @0.55 83.9% vs 80.3%;
                        every one of the 10 feature groups is additive when
                        ablated (-5.9 to -12.7pp each).
  (900, 3600) 15m->1h : DO NOT promote. win@0.65 = 75.5% vs 80.6%; every
                        group is harmful when ablated (+5.5 to +12.7pp).
  (300, 900), (300, 1800), (900, 900), (900, 1800): not better (mixed or
  tiny samples). (1800, 1800) did not complete; (1800, 3600) not rerun.

Run:  python mql_eval.py [--ablate] [--promote 300_3600] [--combo 300_900 ...]
"""

import os
import pickle
import sys
import time
import warnings
import glob

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import ta
from xgboost import XGBClassifier

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from multi_tf_models import (OUT, MODEL_DIR, load_source, build_light_features,
                             build_dataset, walk_forward)
from phase1_validation import wilson_ci, XGB_DEFAULTS
from features.mql_signals import add_mql_features

THETAS = [0.50, 0.55, 0.60, 0.65, 0.70]

GROUPS = {
    'psar':     ['mql_sar_dist_atr', 'mql_sar_flip_since', 'mql_sar_level_dist_atr'],
    'regime':   ['mql_bb_atr_ratio', 'mql_reg_slope_atr'],
    'candle':   ['mql_pat_bull3', 'mql_pat_bear3', 'mql_pat_last', 'mql_ema5_slope_atr'],
    'fractal':  ['mql_frac_since', 'mql_frac_level_atr'],
    'outrev':   ['mql_outrev_bull', 'mql_outrev_bear', 'mql_outrev_since'],
    'macd':     ['mql_macd_state', 'mql_macd_cross_since', 'mql_macd_hist_atr'],
    'fibopiv':  ['mql_pos_prev_day', 'mql_dist_r1_atr', 'mql_dist_s1_atr',
                 'mql_dist_r2_atr', 'mql_dist_s2_atr'],
    'zigzag':   ['mql_zz_dir', 'mql_zz_since', 'mql_zz_retr_618_atr'],
    'midline':  ['mql_ch_mid_dist_atr', 'mql_ch_mid_cross_since'],
    'fosc':     ['mql_fosc', 'mql_fosc_cross_since', 'mql_fosc_pol'],
}
ALL_MQL = [c for g in GROUPS.values() for c in g]


_DS_CACHE = {}


def make_dataset(raw, bar_sec, expiry_sec, use_mql=True, drop_groups=()):
    """Feature dataset with a per-(bar_sec, expiry, variant) cache so all
    expiries of one bar frame reuse the (expensive) feature computation.

    Fair-comparison rule: NaN rows are dropped based on the LIGHT features
    only (identical rows for both variants); mql NaNs are filled with 0,
    exactly like production inference (ml_service fillna).
    """
    key = (id(raw), bar_sec, expiry_sec, use_mql, tuple(sorted(drop_groups)))
    if key in _DS_CACHE:
        return _DS_CACHE[key]
    meta, feats = build_dataset(raw, bar_sec, expiry_sec)
    mql = None
    if use_mql:
        mql = add_mql_features(raw)
        mql = mql.loc[feats.index]
        drop = [c for g in drop_groups for c in GROUPS[g]]
        mql = mql.drop(columns=[c for c in drop if c in mql.columns])
    drop_cols = [c for c in feats.columns] + ['atr', 'fwd']
    full = meta.join(feats)
    if mql is not None:
        full = full.join(mql)
    full = full.dropna(subset=drop_cols)
    if mql is not None:
        for c in mql.columns:
            full[c] = full[c].fillna(0.0)
    meta = full[['datetime', 'symbol', 'atr', 'entry', 'exit', 'fwd', 'label']]
    feats = full[[c for c in full.columns if c not in
                  ('datetime', 'symbol', 'atr', 'entry', 'exit', 'fwd', 'label')]]
    _DS_CACHE[key] = (meta, feats)
    return meta, feats


def evaluate(raw, bar_sec, expiry_sec, use_mql=True, drop_groups=()):
    t0 = time.time()
    meta, feats = make_dataset(raw, bar_sec, expiry_sec, use_mql, drop_groups)
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

    rows = []
    for th in THETAS:
        m = best >= th
        n = int(m.sum())
        w = wins[m].mean() if n else float('nan')
        lo, hi = wilson_ci(n, w) if n else (np.nan, np.nan)
        rows.append({'theta': th, 'n': n, 'win': w * 100 if n else np.nan,
                     'lo': lo * 100, 'hi': hi * 100, 'per_hour': n / (days * 8) if n else 0})
    m = (best >= 0.55) & (hour >= 15) & (hour < 17)
    window = {'n': int(m.sum()), 'win': wins[m].mean() * 100 if m.sum() else np.nan}
    return {'rows': rows, 'window': window, 'test_rows': len(X_te), 'secs': time.time() - t0}


def fmt_row(r):
    return (f'theta={r["theta"]:.2f}: n={r["n"]:6d} win={r["win"]:5.1f}% '
            f'CI=[{r["lo"]:.1f},{r["hi"]:.1f}] per-hour={r["per_hour"]:.2f}')


def compare(raw, bar_sec, expiry_sec, tag=''):
    base = evaluate(raw, bar_sec, expiry_sec, use_mql=False)
    mql = evaluate(raw, bar_sec, expiry_sec, use_mql=True)
    print(f'\n=== [{bar_sec}s -> {expiry_sec}s] {tag} test={mql["test_rows"]:,} '
          f'(baseline {base["secs"]:.0f}s / mql {mql["secs"]:.0f}s)')
    print(f'  WINDOW 15-17 @0.55  baseline: n={base["window"]["n"]} win={base["window"]["win"]:.1f}%'
          f'  |  mql: n={mql["window"]["n"]} win={mql["window"]["win"]:.1f}%')
    for b, m in zip(base['rows'], mql['rows']):
        delta = m['win'] - b['win']
        flag = ' <<< MQL WINS' if delta >= 1.0 else (' (mql worse)' if delta <= -1.0 else '')
        print(f'  base {fmt_row(b)}')
        print(f'  mql  {fmt_row(m)}  d={delta:+.1f}pp{flag}')
    return base, mql


def ablate(raw, bar_sec, expiry_sec):
    """Drop each mql group one at a time; report win@0.65 vs full-mql."""
    full = evaluate(raw, bar_sec, expiry_sec, use_mql=True)
    ref = next(r for r in full['rows'] if r['theta'] == 0.65)
    print(f'\n=== Ablation [{bar_sec}s -> {expiry_sec}s] full-mql win@0.65 = {ref["win"]:.1f}% '
          f'(n={ref["n"]})')
    base = evaluate(raw, bar_sec, expiry_sec, use_mql=False)
    brow = next(r for r in base['rows'] if r['theta'] == 0.65)
    print(f'  baseline(no mql) win@0.65 = {brow["win"]:.1f}% (n={brow["n"]})')
    for g in GROUPS:
        r = evaluate(raw, bar_sec, expiry_sec, use_mql=True, drop_groups=[g])
        row = next(x for x in r['rows'] if x['theta'] == 0.65)
        d = row['win'] - ref['win']
        note = 'additive (keep)' if d <= -0.5 else ('harmful (drop)' if d >= 0.5 else 'neutral')
        print(f'  drop {g:8s}: win@0.65={row["win"]:5.1f}% n={row["n"]:6d} d={d:+.1f}pp [{note}]')


def promote(raw, bar_sec, expiry_sec):
    """Retrain one combo with the mql feature set and save the production
    bundle (same pickle format as multi_tf_models.train_combo)."""
    meta, feats = make_dataset(raw, bar_sec, expiry_sec, use_mql=True)
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
    print(f'promoted [{bar_sec}s -> {expiry_sec}s] rows={len(meta):,} test={len(X_te):,}')
    for th in THETAS:
        m = best >= th
        n = int(m.sum())
        if n:
            w = wins[m].mean()
            lo, hi = wilson_ci(n, w)
            print(f'    theta={th:.2f}: n={n:6d} win={w*100:5.1f}% CI=[{lo*100:.1f},{hi*100:.1f}]')
    m = (best >= 0.55) & (hour >= 15) & (hour < 17)
    if m.sum():
        print(f'    WINDOW 15-17 @0.55: n={int(m.sum())} win={wins[m].mean()*100:.1f}%')
    name = f'combo_{bar_sec}_{expiry_sec}_boot.sav'
    pickle.dump({'model': model, 'features': list(feats.columns),
                 'bar_sec': bar_sec, 'expiry_sec': expiry_sec},
                open(os.path.join(MODEL_DIR, name), 'wb'))
    print(f'    saved {name} with {len(feats.columns)} features '
          f'({len([c for c in feats.columns if c.startswith("mql_")])} mql)')


def main():
    do_ablate = '--ablate' in sys.argv
    promote_args = [a for a in sys.argv if a.startswith('--promote')]
    promote_combo = None
    if promote_args:
        parts = promote_args[0].split('=')
        promote_combo = (int(parts[1].split('_')[0]), int(parts[1].split('_')[1]))
    want = [a for a in sys.argv if '_' in a and a.split('_')[0].isdigit()]

    five = [f for f in glob.glob(os.path.join(OUT, 'five_mins', '*_5_Min*.csv'))]
    fifteen = [f for f in glob.glob(os.path.join(OUT, 'fifteen_mins', '*.csv'))]
    raw5 = load_source(five, 300)
    raw15 = load_source(fifteen, 900)
    raw30 = load_source(fifteen, 1800, from_bar_sec=900)

    combos = [(raw5, 300, e) for e in [900, 1800, 3600]] + \
             [(raw15, 900, e) for e in [900, 1800, 3600]] + \
             [(raw30, 1800, e) for e in [1800, 3600]]
    if want:
        combos = [c for c in combos if f'{c[1]}_{c[2]}' in want]

    if promote_combo:
        bs, es = promote_combo
        if bs == 300:
            promote(raw5, bs, es)
        elif bs == 900:
            promote(raw15, bs, es)
        elif bs == 1800:
            promote(raw30, bs, es)
        print('DONE (promote)')
        return

    for i, (raw, bs, es) in enumerate(combos):
        tag = {'300': '5m', '900': '15m', '1800': '30m'}[str(bs)]
        print(f'--- combo {i + 1}/{len(combos)}: {bs}s -> {es}s '
              f'[{time.strftime("%H:%M:%S")}]', flush=True)
        base, mql = compare(raw, bs, es, tag=tag)
        mql_better = any(
            m['win'] > b['win'] + 0.5 and m['n'] >= max(200, int(b['n'] * 0.8))
            for b, m in zip(base['rows'], mql['rows']))
        if do_ablate:
            ablate(raw, bs, es)
        elif not mql_better:
            print(f'  -> mql NOT better for {bs}s/{es}s; skipping ablation', flush=True)


if __name__ == '__main__':
    main()
