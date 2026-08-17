"""Trade outcome tracker - records fired signals, settles them at expiry
and stores the actual result (win/loss/draw) for the monitor UI.

A trade is recorded when a CALL/PUT signal fires. At expiry the settlement
price is taken from the candle feed (close of the candle at expiry time)
and the result is computed against the entry price.
"""

import csv
import logging
import os
import time
from datetime import datetime, timezone

import pandas as pd

LOGGER = logging.getLogger('dolphin')

TRADES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'trades.csv')

FIELDS = ['id', 'ts', 'symbol', 'tf', 'expiry', 'action', 'candle_open', 'candle_close',
          'entry', 'take_profit', 'stop_loss', 'expiry_time', 'status', 'exit_price', 'result']


class TradeTracker:
    def __init__(self, path=TRADES_PATH):
        self.path = path

    def _read(self):
        if not os.path.exists(self.path):
            return pd.DataFrame(columns=FIELDS)
        try:
            df = pd.read_csv(self.path, dtype={'id': str})
            # pandas may infer float dtypes for all-empty string columns
            for c in ['symbol', 'tf', 'expiry', 'action', 'candle_open', 'candle_close',
                      'entry', 'take_profit', 'stop_loss', 'expiry_time', 'status',
                      'exit_price', 'result']:
                if c in df.columns and df[c].dtype != object:
                    df[c] = df[c].astype(object)
            return df
        except Exception:
            return pd.DataFrame(columns=FIELDS)

    def _write(self, df):
        df.to_csv(self.path, index=False)

    def record(self, d):
        """Record a fired CALL/PUT signal as an open trade (idempotent)."""
        df = self._read()
        key = f"{d['symbol']}_{d['candle_close']}_{d['action']}_{d.get('expiry', '15m')}"
        if len(df) and (df['symbol'].astype(str) + '_' + df['candle_close'].astype(str) + '_' +
                        df['action'].astype(str) + '_' + df['expiry'].astype(str)).isin([key]).any():
            return
        exp_str = str(d.get('expiry', '15m'))
        if exp_str.endswith('h'):
            exp_min = int(exp_str[:-1]) * 60
        else:
            exp_min = int(exp_str.rstrip('m'))
        row = {
            'id': f"{int(time.time())}_{len(df) + 1}",
            'ts': datetime.now(timezone.utc).isoformat(),
            'symbol': d['symbol'],
            'tf': d.get('tf', '5m'),
            'expiry': d.get('expiry', '15m'),
            'action': d['action'],
            'candle_open': d.get('candle_open', ''),
            'candle_close': d.get('candle_close_price', d.get('entry_price', '')),
            'entry': d.get('entry_price', ''),
            'take_profit': d.get('target_price', ''),
            'stop_loss': d.get('stop_loss', ''),
            'expiry_time': d.get('candle_close', ''),
            'status': 'open',
            'exit_price': '',
            'result': '',
        }
        row['expiry_time'] = pd.Timestamp(row['expiry_time']) + pd.Timedelta(minutes=exp_min)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        self._write(df)
        LOGGER.info(f"TRADE RECORDED {row['symbol']} {row['action']} {row['expiry']} "
                    f"expiry at {row['expiry_time']}")
        return row

    def settle(self, candles, now=None):
        """Settle open trades whose expiry time has passed. Returns settled rows."""
        df = self._read()
        if df.empty or not (df['status'] == 'open').any():
            return []
        now = now or datetime.utcnow()
        if 'datetime' not in candles.columns or 't' in candles.columns:
            cd = candles.copy()
            if 'o' in cd.columns:
                cd = cd.rename(columns={'o': 'open', 'h': 'high', 'l': 'low',
                                        'c': 'close', 'v': 'volume'})
            if 'datetime' not in cd.columns and 't' in cd.columns:
                cd['datetime'] = pd.to_datetime(cd['t'], unit='s', utc=True)
            cd['datetime'] = pd.to_datetime(cd['datetime'])
            if cd['datetime'].dt.tz is not None:
                cd['datetime'] = cd['datetime'].dt.tz_localize(None)
            candles = cd
        candle_map = {}
        for sym, grp in candles.groupby('symbol'):
            g = grp.sort_values('datetime')
            candle_map[sym] = dict(zip(g['datetime'].values, g['close'].values))

        settled = []
        for i, row in df.iterrows():
            if row['status'] != 'open':
                continue
            exp_ts = pd.Timestamp(row['expiry_time'])
            if pd.Timestamp(now) < exp_ts:
                continue
            sym = row['symbol']
            closes = candle_map.get(sym)
            if not closes:
                continue
            # settlement = close of the candle at/after expiry time
            best = None
            for ts, c in sorted(closes.items()):
                if pd.Timestamp(ts) >= exp_ts:
                    best = c
                    break
            if best is None:
                continue
            entry = float(row['entry'])
            exit_p = float(best)
            if row['action'] == 'CALL':
                result = 'WIN' if exit_p > entry else ('LOSS' if exit_p < entry else 'DRAW')
            else:
                result = 'WIN' if exit_p < entry else ('LOSS' if exit_p > entry else 'DRAW')
            df.at[i, 'status'] = 'expired'
            df.at[i, 'exit_price'] = round(exit_p, 5)
            df.at[i, 'result'] = result
            settled.append({**row, 'exit_price': round(exit_p, 5), 'result': result,
                            'status': 'expired'})
            LOGGER.info(f"TRADE SETTLED {row['symbol']} {row['action']} "
                        f"entry={row['entry']} exit={exit_p:.5f} -> {result}")
        if settled:
            self._write(df)
        return settled

    def recent(self, n=30):
        df = self._read()
        if df.empty:
            return []
        return df.tail(n).to_dict('records')
