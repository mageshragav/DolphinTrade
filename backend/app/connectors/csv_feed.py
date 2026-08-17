"""Simulation feed: replays the historical 5-min CSVs through the live
platform (DT_FEED=csv). Each cycle advances one candle per symbol, so
signals fire, trades record and settle exactly like live - fully local,
no broker needed.

`history()` returns the full sorted history so trade settlement can look
up expiry prices beyond the current decision window.
"""

import glob
import logging
import os

import pandas as pd

from app.config import DOLPHIN_DIR

LOGGER = logging.getLogger('dolphin')

DEFAULT_CSV_DIR = os.path.join(DOLPHIN_DIR, 'common', 'MachineLearningModel',
                               'output', 'five_mins')


class CSVFeedConnector:
    def __init__(self, csv_dir: str = None, advance: int = 1, window: int = 600):
        self.csv_dir = csv_dir or DEFAULT_CSV_DIR
        self.advance = advance
        self.window = window
        self.data = self._load()
        self._pos = {}
        for sym, grp in self.data.groupby('symbol'):
            self._pos[sym] = 300  # start past the indicator warmup
        LOGGER.info(f'simulation feed: {self.data["symbol"].nunique()} symbols, '
                    f'{len(self.data):,} candles, advance={advance}/cycle')

    def _load(self):
        frames = []
        for f in sorted(glob.glob(os.path.join(self.csv_dir, '*_5_Min*.csv'))):
            try:
                df = pd.read_csv(f)
            except Exception as e:
                LOGGER.warning(f'skip {f}: {e}')
                continue
            df['symbol'] = 'FX:' + os.path.basename(f).split('_')[0]
            frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def fetch_candles(self, pairs, size=600) -> pd.DataFrame:
        out = []
        for sym, grp in self.data.groupby('symbol'):
            n = len(grp)
            pos = min(self._pos.get(sym, 300), n)
            win = grp.iloc[max(0, pos - self.window):pos]
            if len(win):
                out.append(win)
            self._pos[sym] = pos + self.advance
        return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

    def history(self) -> pd.DataFrame:
        """Full sorted history - used for trade settlement in sim mode."""
        return self.data

    def place_bet(self, symbol, direction, amount, duration_sec=None,
                  order_type='binary', multiplicator=100,
                  take_profit=None, stop_loss=None) -> dict:
        """Synthetic broker deal so dry-run-off sim exercises the full
        place -> record -> settle chain end to end (no real order)."""
        self._bet_seq = getattr(self, '_bet_seq', 0) + 1
        grp = self.data[self.data['symbol'] == 'FX:' + symbol.split(':')[-1]]
        last = float(grp['close'].iloc[-1]) if len(grp) else 1.0
        import time
        return {
            'id': f'fake-{self._bet_seq}',
            'curs_open': last,
            'winperc': 90,
            'time_close_default': time.time() + (duration_sec or 3600),
            'status': 'proceed',
        }

    def disconnect(self):
        pass
