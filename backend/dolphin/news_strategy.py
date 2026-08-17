"""News-Event Momentum strategy (live channel).

Backtest verdict (news_backtest.py, Dec 2023 - Jul 2024): weak and
sample-thin - 15m spike continuation ~52-65% (n=17-20, CI crosses 50%),
30m no edge, 1h inconsistent. The documented 65-75% continuation edge does
not reproduce at 5-min grid granularity. This module is therefore built as
a measurement channel: it fires only for STRONG spikes (|body| >= 0.5 ATR)
and every fired signal is logged for live validation before real stakes.

Modes:
  cont  trade WITH strong spikes, 15m expiry (best backtest read)
  fade  trade AGAINST strong spikes, 1h expiry (5m-bar backtest read ~60%)

Event sources (checked in order):
  --news-events FILE : CSV rows: date,time_utc(HH:MM),currency,impact,title
  calendar module    : ForexFactory feed when it responds

Live detection: the first COMPLETED 5m candle starting at/after the release
time; its body vs the pre-event ATR decides the spike. Entry = spike close,
signal fired within [release+2m, release+7m].

Run (inside the live loop):  python live_loop.py --news-events events.csv
"""

import logging
import os

import numpy as np
import pandas as pd
import ta

LOGGER = logging.getLogger('dolphin')

SPIKE_ATR = 0.5          # min |body| in ATR units to call it a real spike
FIRE_WINDOW_MIN = (2, 7)  # minutes after release when the signal may fire
PAYOUT = 0.90
SLIPPAGE_TAX = 0.02
STAKE_PCT = 0.01

PAIR_CURRENCY = {'EURUSD': 'USD', 'EURCAD': 'EUR', 'EURJPY': 'EUR', 'EURGBP': 'EUR',
                 'EURAUD': 'EUR', 'GBPUSD': 'GBP', 'USDCAD': 'USD', 'USDJPY': 'USD',
                 'AUDUSD': 'USD'}


def load_events_file(path):
    """CSV: date,time_utc,currency,impact,title"""
    df = pd.read_csv(path)
    ev = []
    for _, r in df.iterrows():
        ev.append({
            'time': pd.Timestamp(f"{r['date']} {str(r['time_utc']).strip()}"),
            'currency': str(r['currency']).upper(),
            'impact': str(r['impact']).lower(),
            'title': str(r['title']),
        })
    return ev


class NewsMomentumStrategy:
    def __init__(self, events=None, mode='cont', spike_atr=SPIKE_ATR, theta=0.0):
        """events: list of dicts with time/currency/impact/title; mode cont|fade."""
        self.events = events or []
        self.mode = mode
        self.spike_atr = spike_atr
        self.theta = theta

    def relevant(self, symbol):
        cur = PAIR_CURRENCY.get(symbol.split(':')[-1], 'USD')
        return [e for e in self.events if e['currency'] in (cur, 'ALL') and e['impact'] == 'high']

    def check(self, candles, now=None):
        """Evaluate the strategy for every symbol. Returns decision dicts.

        candles: normalized 5m frame (datetime/symbol/open/high/low/close).
        Fires only within FIRE_WINDOW_MIN after a release and only for
        spikes >= spike_atr. Decisions are tagged 'EVENT' for the alert.
        """
        now = pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow().tz_localize(None)
        out = []
        for symbol, grp in candles.groupby('symbol'):
            events = self.relevant(symbol)
            for e in events:
                age_min = (now - e['time']).total_seconds() / 60.0
                if not (FIRE_WINDOW_MIN[0] <= age_min <= FIRE_WINDOW_MIN[1]):
                    continue
                df = grp.sort_values('datetime').reset_index(drop=True)
                cand = df[df['datetime'] >= e['time']]
                if cand.empty:
                    continue
                i0 = cand.index[0]
                if (df['datetime'].iloc[i0] - e['time']).total_seconds() > 900:
                    continue  # market closed at release
                if i0 < 15 or i0 + 1 >= len(df):
                    continue
                atr = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
                a = atr.iloc[i0 - 1]
                body = df['close'].iloc[i0] - df['open'].iloc[i0]
                if np.isnan(a) or a <= 0 or abs(body) < self.spike_atr * a:
                    continue
                spike_up = body > 0
                if self.mode == 'cont':
                    direction = 'CALL' if spike_up else 'PUT'
                    expiry = '15m'
                else:
                    direction = 'PUT' if spike_up else 'CALL'
                    expiry = '1h'
                entry = float(df['close'].iloc[i0])
                out.append({
                    'symbol': symbol,
                    'tf': '5m',
                    'expiry': expiry,
                    'action': direction,
                    'best_prob': min(0.65, 0.5 + abs(body) / a * 0.15),
                    'ev_score': 0.0,
                    'stake': 0.0,
                    'news_veto': False,
                    'model': f'EVENT-{self.mode}',
                    'strategy': 'event',
                    'event_title': e['title'],
                    'spike_atr': round(abs(body) / a, 2),
                    'entry_price': round(entry, 5),
                    'candle_close': str(df['datetime'].iloc[i0]),
                    'rationale': f'EVENT {e["title"]} spike {abs(body)/a:.2f}x ATR '
                                 f'{"up" if spike_up else "down"} -> {direction}',
                })
        return out
