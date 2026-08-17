"""News-Event Momentum backtest.

Strategy: at a high-impact release, the first 5-minute candle's direction is
the trade direction (spike continuation). Entry = spike candle close, expiry
15m/30m/1h later. Only trade when the spike is real (|body| >= k*ATR).

Events: curated public-knowledge list (US macro 12:30/13:30 UTC by DST,
FOMC 18:00, ECB 12:15/13:15, BoE 12:00, BoJ 03:00). Times are approximate
to the 5-min grid; the nearest candle at/after the release is used.

Run:  python news_backtest.py
"""

import glob
import os
import sys
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import ta

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)
from phase1_validation import wilson_ci

OUT = os.path.join(CURR, 'common', 'MachineLearningModel', 'output', 'five_mins')

# (date, hour_utc, minute_utc, currency, impact, title)
EVENTS = [
    # March 2024 (US DST from Mar 10; ECB DST from Mar 31)
    ('2024-03-07', 13, 15, 'EUR', 'high', 'ECB rate decision'),
    ('2024-03-08', 13, 30, 'USD', 'high', 'US NFP'),
    ('2024-03-12', 12, 30, 'USD', 'high', 'US CPI'),
    ('2024-03-14', 12, 30, 'USD', 'medium', 'US PPI'),
    ('2024-03-19', 3, 0, 'JPY', 'high', 'BoJ rate decision'),
    ('2024-03-20', 18, 0, 'USD', 'high', 'FOMC decision'),
    ('2024-03-21', 12, 0, 'GBP', 'high', 'BoE rate decision'),
    # April 2024
    ('2024-04-05', 12, 30, 'USD', 'high', 'US NFP'),
    ('2024-04-10', 12, 30, 'USD', 'high', 'US CPI'),
    ('2024-04-11', 12, 15, 'EUR', 'high', 'ECB rate decision'),
    ('2024-04-11', 12, 30, 'USD', 'medium', 'US PPI'),
    ('2024-04-15', 12, 30, 'USD', 'medium', 'US retail sales'),
    ('2024-04-26', 3, 0, 'JPY', 'high', 'BoJ rate decision'),
    # May 2024
    ('2024-05-01', 18, 0, 'USD', 'high', 'FOMC decision'),
    ('2024-05-03', 12, 30, 'USD', 'high', 'US NFP'),
    ('2024-05-09', 12, 0, 'GBP', 'high', 'BoE rate decision'),
    ('2024-05-14', 12, 30, 'USD', 'medium', 'US PPI'),
    ('2024-05-15', 12, 30, 'USD', 'high', 'US CPI'),
    # June 2024
    ('2024-06-06', 12, 15, 'EUR', 'high', 'ECB rate decision'),
    ('2024-06-07', 12, 30, 'USD', 'high', 'US NFP'),
    ('2024-06-12', 12, 30, 'USD', 'high', 'US CPI'),
    ('2024-06-12', 18, 0, 'USD', 'high', 'FOMC decision'),
    ('2024-06-13', 12, 30, 'USD', 'medium', 'US PPI'),
    ('2024-06-14', 3, 0, 'JPY', 'high', 'BoJ rate decision'),
    ('2024-06-18', 12, 30, 'USD', 'medium', 'US retail sales'),
    ('2024-06-20', 12, 0, 'GBP', 'high', 'BoE rate decision'),
    # July 2024
    ('2024-07-05', 12, 30, 'USD', 'high', 'US NFP'),
    ('2024-07-11', 12, 30, 'USD', 'high', 'US CPI'),
    ('2024-07-12', 12, 30, 'USD', 'medium', 'US PPI'),
    ('2024-07-16', 12, 30, 'USD', 'medium', 'US retail sales'),
    ('2024-07-31', 18, 0, 'USD', 'high', 'FOMC decision'),
]

USD_PAIRS = ['EURUSD', 'GBPUSD', 'USDCAD', 'USDJPY', 'EURAUD']
EUR_PAIRS = ['EURUSD', 'EURCAD', 'EURJPY', 'EURGBP', 'EURAUD']
GBP_PAIRS = ['GBPUSD', 'EURGBP']
JPY_PAIRS = ['EURJPY', 'USDJPY']


def event_pairs(currency):
    if currency == 'USD':
        return USD_PAIRS
    if currency == 'EUR':
        return EUR_PAIRS
    if currency == 'GBP':
        return GBP_PAIRS
    if currency == 'JPY':
        return JPY_PAIRS
    return []


def load_pairs():
    data = {}
    for f in sorted(glob.glob(os.path.join(OUT, '*_5_Min*.csv'))):
        df = pd.read_csv(f)
        df['datetime'] = pd.to_datetime(df['datetime'])
        sym = os.path.basename(f).split('_')[0]
        if sym in data:
            data[sym] = pd.concat([data[sym], df]).drop_duplicates('datetime')
        else:
            data[sym] = df
    for sym in data:
        data[sym] = data[sym].sort_values('datetime').reset_index(drop=True)
    return data


def main():
    data = load_pairs()
    print(f'pairs loaded: {len(data)}')

    rows = []
    for date, hh, mm, cur, impact, title in EVENTS:
        ev_ts = pd.Timestamp(f'{date} {hh:02d}:{mm:02d}:00')
        for sym in event_pairs(cur):
            df = data.get(sym)
            if df is None:
                continue
            atr = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
            cand = df[df['datetime'] >= ev_ts]
            if cand.empty:
                continue
            i0 = df.index.get_loc(cand.index[0])
            if (df['datetime'].iloc[i0] - ev_ts).total_seconds() > 900:
                continue  # event too far from the grid (market closed)
            if i0 < 15 or i0 + 12 >= len(df):
                continue
            body = df['close'].iloc[i0] - df['open'].iloc[i0]
            if body == 0:
                continue
            a = atr.iloc[i0 - 1]
            if np.isnan(a):
                continue
            for k, exp in [(3, '15m'), (6, '30m'), (12, '1h')]:
                fwd = df['close'].iloc[i0 + k] - df['close'].iloc[i0]
                win = (fwd > 0) == (body > 0)
                rows.append({
                    'sym': sym, 'event': title, 'date': date, 'impact': impact,
                    'exp': exp, 'body_atr': body / a, 'win': win,
                })
    res = pd.DataFrame(rows)
    print(f'samples: {len(res)}')

    for exp in ['15m', '30m', '1h']:
        for thr in [0.0, 0.3, 0.5, 0.8]:
            m = (res['exp'] == exp) & (res['body_atr'].abs() >= thr)
            n = int(m.sum())
            if n < 10:
                continue
            w = res.loc[m, 'win'].mean()
            lo, hi = wilson_ci(n, w)
            print(f'  exp={exp:>3s} |body|>={thr}: n={n:4d} win={w*100:5.1f}% CI=[{lo*100:.1f},{hi*100:.1f}] '
                  f'({res.loc[m,"date"].nunique()} event-days)')
    print()
    print('  by impact (exp 15m, |body|>=0.3):')
    for imp in ['high', 'medium']:
        m = (res['exp'] == '15m') & (res['impact'] == imp) & (res['body_atr'].abs() >= 0.3)
        n = int(m.sum())
        if n >= 10:
            print(f'    {imp:6s}: n={n:4d} win={res.loc[m,"win"].mean()*100:5.1f}%')
    print()
    print('  by month (exp 15m, |body|>=0.3):')
    for mo, g in res[(res['exp'] == '15m') & (res['body_atr'].abs() >= 0.3)].groupby(res['date'].str[:7]):
        n = len(g)
        if n >= 10:
            print(f'    {mo}: n={n:4d} win={g["win"].mean()*100:5.1f}%')
    print()
    print('  by pair (exp 15m, |body|>=0.3, n>=15):')
    for sym, g in res[(res['exp'] == '15m') & (res['body_atr'].abs() >= 0.3)].groupby('sym'):
        if len(g) >= 15:
            print(f'    {sym:8s}: n={len(g):4d} win={g["win"].mean()*100:5.1f}%')


if __name__ == '__main__':
    main()
