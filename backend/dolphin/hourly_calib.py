"""Hourly-guarantee calibration: coverage, win rate and EV of the hourly-max
pick per floor, over the walk-forward test slices of all 8 combos.

The picker semantics: within each UTC hour, the highest-best_prob candidate
across all (symbol, combo, bar) rows is the one the hourly scan would place;
an hour is 'covered' when that pick clears the floor.

Run:  python hourly_calib.py
"""

import glob
import os
import sys
import time
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from multi_tf_models import OUT, load_source, walk_forward
from phase1_validation import XGB_DEFAULTS
from mql_eval import make_dataset

FLOORS = [0.55, 0.58, 0.60, 0.62, 0.65]
PAYOUT = 0.88            # 0.90 minus the 2% slippage tax


def main():
    t0 = time.time()
    five = [f for f in glob.glob(os.path.join(OUT, 'five_mins', '*_5_Min*.csv'))]
    fifteen = [f for f in glob.glob(os.path.join(OUT, 'fifteen_mins', '*.csv'))]
    raw5 = load_source(five, 300)
    raw15 = load_source(fifteen, 900)
    raw30 = load_source(fifteen, 1800, from_bar_sec=900)
    combos = ([(raw5, 300, e) for e in [900, 1800, 3600]] +
              [(raw15, 900, e) for e in [900, 1800, 3600]] +
              [(raw30, 1800, e) for e in [1800, 3600]])

    frames = []
    for i, (raw, bs, es) in enumerate(combos):
        use_mql = (bs, es) == (300, 3600)      # match production bundles
        print(f'--- [{i+1}/{len(combos)}] {bs}s -> {es}s '
              f'[mql={use_mql}] {time.strftime("%H:%M:%S")}', flush=True)
        meta, feats = make_dataset(raw, bs, es, use_mql=use_mql)
        X_tr, y_tr, X_te, y_te, m_te = walk_forward(feats, meta)
        model = XGBClassifier(**XGB_DEFAULTS)
        model.fit(X_tr, y_tr)
        P = model.predict_proba(X_te)
        best = np.maximum(P[:, 1], P[:, 2])
        direction = np.where(P[:, 1] >= P[:, 2], 1, 2)
        actual = np.where(m_te['fwd'].values > 0, 1,
                          np.where(m_te['fwd'].values < 0, 2, 0))
        win = (direction == actual) & (actual != 0)
        frames.append(pd.DataFrame({
            'dt': pd.to_datetime(m_te['datetime']).values,
            'best': best, 'win': win}))
        print(f'  test rows: {len(X_te):,} ({time.time()-t0:.0f}s)', flush=True)

    allr = pd.concat(frames, ignore_index=True)
    allr['hour'] = allr['dt'].dt.floor('h')
    hours_total = int(allr['hour'].nunique())
    print(f'\n== candidates: {len(allr):,} | hours: {hours_total:,} | '
          f'({time.time()-t0:.0f}s)', flush=True)

    # the hourly-max pick per hour
    picks = allr.sort_values('best').groupby('hour', sort=False).tail(1)
    print(f'== hours with >=1 candidate above 0.50: {len(picks)}', flush=True)

    print(f'\n{"floor":>6} {"hours":>6} {"coverage":>9} {"win":>7} {"EV":>7}')
    for f in FLOORS:
        m = picks[picks['best'] >= f]
        n = int(len(m))
        cov = n / hours_total * 100.0
        w = float(m['win'].mean()) if n else float('nan')
        ev = w * PAYOUT - (1 - w) if n else float('nan')
        print(f'{f:>6.2f} {n:>6} {cov:>8.1f}% {w*100:>6.1f}% {ev:>7.3f}')

    # window-mode view (15-17 UTC) for reference
    wh = allr[(allr['hour'].dt.hour >= 15) & (allr['hour'].dt.hour < 17)]
    if len(wh):
        wp = wh.sort_values('best').groupby('hour', sort=False).tail(1)
        print(f'\n== 15-17 UTC window only: hours={len(wp)}')
        for f in FLOORS:
            m = wp[wp['best'] >= f]
            n = int(len(m))
            if not n:
                continue
            w = float(m['win'].mean())
            print(f'   floor={f:.2f}: {n} hours covered ({n/len(wp)*100:.0f}%), '
                  f'win={w*100:.1f}% EV={w*PAYOUT-(1-w):.3f}')
    print(f'\nDONE ({time.time()-t0:.0f}s)')


if __name__ == '__main__':
    main()
