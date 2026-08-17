"""Broker-feed candle collector: the missing data foundation.

Olymp/Quotex have no public REST API for candles, but the websocket channel
(v1's Olymptradeconnect) returns them. This collector polls that channel
continuously and persists candles in the exact format the feature pipeline
consumes (datetime,symbol,open,high,low,close,volume[,spread_bps]).

Training the models on this feed instead of TradingView mid-price is the
single biggest honest win-rate improvement still available (entry/exit
prices, spread and B-book behavior are then identical between training and
live execution).

Run:  python broker_feed.py --pairs EURUSD_OTC,GBPUSD_OTC --out broker_candles
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from common.socketconnect.Olymptradeconnect import OlympTradeClient

CANDLE_COLS = ['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'spread_bps']


class BrokerFeedCollector:
    def __init__(self, out_dir='broker_candles', poll_seconds=30, candles_per_poll=120):
        self.out_dir = out_dir
        self.poll_seconds = poll_seconds
        self.candles_per_poll = candles_per_poll
        self.client = None
        os.makedirs(out_dir, exist_ok=True)

    def _connect(self):
        if self.client is None:
            self.client = OlympTradeClient(group='demo')
        return self.client

    def _disconnect(self):
        if self.client is not None:
            try:
                self.client.disconnect()
            except Exception:
                pass
            self.client = None

    def fetch(self, pair):
        """Fetch candles; normalizes o/h/l/c/v/t + optional spread."""
        data = self._connect().get_candle(size=self.candles_per_poll, pair=pair)
        if not data:
            return None
        candles = data[0].get('candles') if isinstance(data, list) else data.get('candles')
        if not candles:
            return None
        df = pd.DataFrame(candles)
        if 'o' in df.columns:
            df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low',
                                    'c': 'close', 'v': 'volume'})
        df['datetime'] = pd.to_datetime(df['t'], unit='s', utc=True)
        df = df.sort_values('datetime').drop_duplicates('datetime')
        df['symbol'] = pair
        for col in CANDLE_COLS:
            if col not in df.columns:
                df[col] = 0.0 if col != 'symbol' else pair
        return df[CANDLE_COLS]

    def append(self, df, pair):
        path = os.path.join(self.out_dir, f'{pair}.csv')
        if os.path.exists(path):
            old = pd.read_csv(path, parse_dates=['datetime'])
            df = pd.concat([old, df]).drop_duplicates('datetime').sort_values('datetime')
        df.to_csv(path, index=False)
        return len(df)

    def run_forever(self, pairs):
        print(f'collecting {pairs} every {self.poll_seconds}s -> {self.out_dir}')
        while True:
            try:
                for pair in pairs:
                    try:
                        df = self.fetch(pair)
                        if df is not None and len(df):
                            n = self.append(df, pair)
                            print(f'{datetime.now(timezone.utc):%H:%M:%S} {pair}: {n} rows', flush=True)
                    except Exception as e:
                        print(f'{pair} fetch error: {e}', flush=True)
                        self._disconnect()
                        time.sleep(5)
                time.sleep(self.poll_seconds)
            except KeyboardInterrupt:
                self._disconnect()
                break


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--pairs', default='EURUSD_OTC,GBPUSD_OTC')
    ap.add_argument('--out', default='broker_candles')
    ap.add_argument('--poll', type=int, default=30)
    ap.add_argument('--candles', type=int, default=120)
    args = ap.parse_args()
    collector = BrokerFeedCollector(out_dir=args.out, poll_seconds=args.poll,
                                    candles_per_poll=args.candles)
    collector.run_forever([p.strip() for p in args.pairs.split(',') if p.strip()])
