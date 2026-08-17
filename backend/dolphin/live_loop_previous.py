"""PREVIOUS VERSION of live_loop.py (backup).

This is the version WITHOUT the window mode (--hours) and probability gate
(--theta) flags. It uses the fixed 0.65 gate via DecisionService defaults and
runs at every 5-minute candle close regardless of the hour.

Everything else is identical to the current live_loop.py (alerts, verify,
forming-candle handling, olymp/csv feeds, telegram/notify/sound).

Run:  python live_loop_previous.py [--feed olymp] [--once] [--live] ...

Live decision loop: runs at every 5-minute candle close.

Scheduling (no cron drift): aligned to the 5-min epoch boundary; waits
LATENCY_SEC after the boundary so the candle is closed and collectable,
then fetches the watchlist, computes features, decides, logs, and (in live
mode) places the bet via the olymp websocket.

When a CALL/PUT signal fires you are alerted immediately so you know it is
time to enter (the decision is made AFTER the candle closes - never at the
candle open - so the signal is confirmed, not guessed):
  - console banner
  - desktop notification (notify-send)
  - sound beep (aplay/paplay)
  - Telegram message to GROUP_ID (requires network + configured bot)

Modes:
  --feed csv   : simulate the live feed from local CSVs (offline testing)
  --feed olymp : live websocket feed (requires a valid broker session)

Run:
  python live_loop_previous.py --feed csv --once
  python live_loop_previous.py --feed olymp --pairs EURUSD,GBPUSD
  python live_loop_previous.py --feed olymp --alert telegram   # phone alerts only
"""

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone

import pandas as pd

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from ml_service import DecisionService

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
LOGGER = logging.getLogger('dolphin')

WATCHLIST = ['EURUSD', 'EURCAD', 'EURJPY', 'EURGBP', 'EURAUD', 'GBPUSD', 'USDCAD', 'USDJPY']
BAR_SEC = 300
LATENCY_SEC = 30          # wait after candle close before fetching
FETCH_CANDLES = 300       # olymp WS history depth
LOG_PATH = os.path.join(CURR, 'decision_logs.csv')
SIGNALS_PATH = os.path.join(CURR, 'signals.csv')

_BEEP_PATH = '/tmp/dolphin_beep.wav'
_telegram_bot = None


def _make_beep():
    """Generate a short double-beep wav so no external sound file is needed."""
    try:
        import math
        import struct
        rate = 44100
        frames = bytearray()
        for freq, dur in [(880, 0.15), (660, 0.15)]:
            n = int(rate * dur)
            for i in range(n):
                env = min(1.0, i / 200.0, (n - i) / 200.0)
                frames += struct.pack('<h', int(12000 * env * math.sin(2 * math.pi * freq * i / rate)))
        with wave.open(_BEEP_PATH, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(frames))
        return True
    except Exception:
        return False


def _get_telegram_bot():
    global _telegram_bot
    if _telegram_bot is None:
        try:
            from common.constants import BOT_TOKEN, GROUP_ID
            import telebot
            _telegram_bot = (telebot.TeleBot(BOT_TOKEN), GROUP_ID)
        except Exception as e:
            LOGGER.warning(f'telegram unavailable: {e}')
            _telegram_bot = False
    return _telegram_bot if _telegram_bot else None


def _fmt_server_time(candle_close_str, tz_offset_hours):
    """Convert a naive-UTC candle time string to broker server time."""
    try:
        ts = pd.to_datetime(candle_close_str)
        return (ts + pd.Timedelta(hours=tz_offset_hours)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(candle_close_str)


def alert_signal(d, channels='all', tz_offset=3):
    """Tell the trader it is time to enter. Never raises."""
    if d['action'] not in ('CALL', 'PUT'):
        return
    msg = (f'\n*** DOLPHIN TRADE SIGNAL ***\n'
           f'SYMBOL   : {d["symbol"]}\n'
           f'DIRECTION: {d["action"]} ({"UP" if d["action"] == "CALL" else "DOWN"})\n'
           f'ENTER NOW: within the next 60 seconds\n'
           f'EXPIRY   : {d["expiry"]}\n'
           f'STAKE    : ${d["stake"]:.2f}\n'
           f'P        : {d["best_prob"]:.3f} (gate {d.get("gate", 0.65)})\n'
           f'EV       : {d["ev_score"]:+.3f}\n'
           f'CANDLE   : {d["candle_close"]} UTC  ({_fmt_server_time(d["candle_close"], tz_offset)} server+{tz_offset})\n'
           f'CANDLE O : {d.get("candle_open", "-")}   H: {d.get("candle_high", "-")}\n'
           f'CANDLE L : {d.get("candle_low", "-")}    C: {d.get("candle_close_price", "-")}\n'
           f'ENTRY    : {d.get("entry_price", "-")}   ATR: {d.get("atr", "-")}\n'
           f'TARGET   : {d.get("target_price", "-")}  (1x ATR)\n'
           f'STOP     : {d.get("stop_loss", "-")}  (invalidation 0.5x ATR)')
    LOGGER.info(msg)
    try:
        if channels in ('all', 'notify') and shutil.which('notify-send'):
            subprocess.run(['notify-send', 'DOLPHIN TRADE SIGNAL',
                            f"{d['symbol']} {d['action']} now - P={d['best_prob']}"],
                           timeout=5)
    except Exception:
        pass
    try:
        if channels in ('all', 'sound'):
            if not os.path.exists(_BEEP_PATH):
                _make_beep()
            if os.path.exists(_BEEP_PATH):
                if shutil.which('paplay'):
                    subprocess.run(['paplay', _BEEP_PATH], timeout=5)
                elif shutil.which('aplay'):
                    subprocess.run(['aplay', '-q', _BEEP_PATH], timeout=5)
    except Exception:
        pass
    try:
        if channels in ('all', 'telegram'):
            bot = _get_telegram_bot()
            if bot:
                bot[0].send_message(chat_id=bot[1], text=msg)
    except Exception as e:
        LOGGER.warning(f'telegram send failed: {e}')


def next_boundary(now_ts):
    return (now_ts // BAR_SEC + 1) * BAR_SEC


class CSVFeed:
    def __init__(self, out_dir):
        import glob
        files = sorted(glob.glob(os.path.join(out_dir, '*_5_Min*.csv')))
        frames = []
        for f in files:
            df = pd.read_csv(f)
            df['symbol'] = 'FX:' + os.path.basename(f).split('_')[0]
            frames.append(df)
        self.data = pd.concat(frames, ignore_index=True)

    def get_candles(self, pairs, size=300):
        # emulate the live window: the newest `size` candles per symbol
        out = []
        for _, grp in self.data.groupby('symbol'):
            out.append(grp.tail(size))
        return pd.concat(out, ignore_index=True)


class OlympFeed:
    def __init__(self, pairs):
        from common.socketconnect.Olymptradeconnect import OlympTradeClient
        self.client = OlympTradeClient(group='demo')
        self.pairs = pairs

    def get_candles(self, pairs, size=300):
        frames = []
        for p in pairs:
            data = self.client.get_candle(size=size, pair=p)
            if not data:
                continue
            candles = data[0].get('candles') if isinstance(data, list) else data.get('candles')
            if not candles:
                continue
            df = pd.DataFrame(candles)
            df['symbol'] = p
            frames.append(df)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def place_bet(self, symbol, direction, amount, duration=300):
        return self.client.get_bet(direction, symbol, amount=amount, duration=str(duration))


def verify_reference(candles, tz_offset=3):
    """Print the last COMPLETED candle per symbol - the exact candle the
    decision uses - so it can be eyeballed against the platform chart."""
    if candles is None or candles.empty:
        return
    raw = candles.copy()
    if 'o' in raw.columns:
        raw = raw.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close'})
    if 'datetime' not in raw.columns and 't' in raw.columns:
        raw['datetime'] = pd.to_datetime(raw['t'], unit='s', utc=True).dt.tz_localize(None)
    raw['datetime'] = pd.to_datetime(raw['datetime'])
    if raw['datetime'].dt.tz is not None:
        raw['datetime'] = raw['datetime'].dt.tz_localize(None)
    if len(raw):
        feed_newest = raw['datetime'].max()
        now_utc = pd.Timestamp.utcnow().tz_localize(None)
        if abs((now_utc - feed_newest).total_seconds()) < 24 * 3600:
            newest_per_symbol = raw.groupby('symbol')['datetime'].transform('max')
            raw = raw[raw['datetime'] < newest_per_symbol]
    LOGGER.info('--- last completed candle (the one the decision uses) ---')
    for _, grp in raw.groupby('symbol', sort=False):
        row = grp.sort_values('datetime').iloc[-1]
        utc = row['datetime']
        LOGGER.info(f"  {row['symbol']:10s} {utc} UTC  "
                    f"({(utc + pd.Timedelta(hours=tz_offset)).strftime('%Y-%m-%d %H:%M:%S')} server+{tz_offset})  "
                    f"O {float(row['open']):.5f}  H {float(row['high']):.5f}  "
                    f"L {float(row['low']):.5f}  C {float(row['close']):.5f}")


def run_once(feed, service, equity, live=False, alert='all', tz_offset=3, verify=False):
    candles = feed.get_candles(WATCHLIST, FETCH_CANDLES)
    if verify:
        verify_reference(candles, tz_offset)
    decisions = service.decide_all(candles, equity=equity)
    header = not os.path.exists(LOG_PATH)
    rows = []
    fired = [d for d in decisions if d['action'] in ('CALL', 'PUT')]
    for d in decisions:
        LOGGER.info(f"{d['symbol']}: {d['action']}  P={d['best_prob']}  "
                    f"ev={d['ev_score']}  ({d['rationale']})")
        rows.append({'ts': datetime.now(timezone.utc).isoformat(), **d})
        if live and d['action'] in ('CALL', 'PUT') and d['stake'] > 0:
            try:
                resp = feed.place_bet(d['symbol'], 'up' if d['action'] == 'CALL' else 'down',
                                      amount=str(d['stake']))
                LOGGER.info(f"BET placed {d['symbol']} {d['action']} -> {resp}")
                d['bet_placed'] = True
            except Exception as e:
                LOGGER.error(f'bet failed for {d["symbol"]}: {e}')
                d['bet_placed'] = False
    pd.DataFrame(rows).to_csv(LOG_PATH, mode='a', header=header, index=False)

    if fired:
        sig = pd.DataFrame([{'ts': datetime.now(timezone.utc).isoformat(), **d} for d in fired])
        sig.to_csv(SIGNALS_PATH, mode='a', header=not os.path.exists(SIGNALS_PATH), index=False)
        for d in fired:
            alert_signal(d, channels=alert, tz_offset=tz_offset)
    else:
        best = max(decisions, key=lambda x: x['best_prob']) if decisions else None
        if best:
            LOGGER.info(f'no signal this cycle (closest: {best["symbol"]} '
                        f'P={best["best_prob"]:.3f}, need >= {service.theta})')
    return decisions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--feed', choices=['csv', 'olymp'], default='olymp',
                    help='olymp = live broker feed (default); csv = offline simulation')
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--live', action='store_true', help='actually place bets (olymp feed only)')
    ap.add_argument('--alert', choices=['all', 'telegram', 'notify', 'sound', 'none'], default='all',
                    help='how to alert when a signal fires (default: all)')
    ap.add_argument('--tz-offset', type=int, default=3,
                    help='broker server timezone offset from UTC for chart matching (default: 3)')
    ap.add_argument('--verify', action='store_true',
                    help='print the last completed candle per symbol each cycle (chart cross-check)')
    ap.add_argument('--pairs', default=','.join(WATCHLIST))
    ap.add_argument('--equity', type=float, default=1000.0)
    ap.add_argument('--csv-dir', default=os.path.join(CURR, 'common', 'MachineLearningModel', 'output', 'five_mins'))
    args = ap.parse_args()

    service = DecisionService()
    if args.feed == 'csv':
        feed = CSVFeed(args.csv_dir)
    else:
        feed = OlympFeed([p.strip() for p in args.pairs.split(',')])

    if args.once:
        run_once(feed, service, args.equity, live=args.live and args.feed == 'olymp', alert=args.alert, tz_offset=args.tz_offset, verify=args.verify)
        return

    LOGGER.info(f'live loop started ({args.feed}) - next boundary in '
                f'{next_boundary(time.time()) - time.time():.0f}s')
    while True:
        now = time.time()
        boundary = next_boundary(now)
        sleep_s = boundary - now + LATENCY_SEC
        time.sleep(max(sleep_s, 1))
        try:
            run_once(feed, service, args.equity, live=args.live and args.feed == 'olymp', alert=args.alert, tz_offset=args.tz_offset, verify=args.verify)
        except Exception as e:
            LOGGER.exception(f'decision cycle failed: {e}')


if __name__ == '__main__':
    main()
