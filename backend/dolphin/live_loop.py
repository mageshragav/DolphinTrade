"""Live decision loop - multi-timeframe (Phase 3).

Unified scheduler: checks every active combo's bar boundary each tick.
A combo is (bar_sec, expiry_sec), e.g. 5m candles with 15m expiry, 15m
candles with 1h expiry, etc. Candles are always fetched as the 5m native
olymp feed and resampled inside the service for higher timeframes.

Bet duration = the combo's expiry (fixed the 300s-vs-900s mismatch).

When a CALL/PUT signal fires you are alerted immediately:
  - console banner, desktop notification, sound beep, Telegram
  - entry/target/stop levels + candle OHLC in both UTC and broker time

Run:
  python live_loop.py                                    # default combos
  python live_loop.py --combos 5m:15m,5m:30m,5m:1h       # chosen combos
  python live_loop.py --hours 15-17 --theta 0.55         # window mode
  python live_loop.py --live                             # place bets
  python live_loop.py --feed csv --once                  # offline test
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

from ml_service import DecisionService, DEFAULT_COMBOS

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
LOGGER = logging.getLogger('dolphin')

WATCHLIST = ['EURUSD', 'EURCAD', 'EURJPY', 'EURGBP', 'EURAUD', 'GBPUSD', 'USDCAD', 'USDJPY']
LATENCY_SEC = 30          # wait after bar close before deciding
FETCH_CANDLES = 600       # olymp WS history depth (5m native bars)
LOG_PATH = os.path.join(CURR, 'decision_logs.csv')
SIGNALS_PATH = os.path.join(CURR, 'signals.csv')

_BEEP_PATH = '/tmp/dolphin_beep.wav'
_telegram_bot = None


def _to_secs(s):
    s = s.strip().lower()
    if s.endswith('h'):
        return int(s[:-1]) * 3600
    if s.endswith('m'):
        return int(s[:-1]) * 60
    return int(s) * 60


def parse_combos(spec):
    out = []
    for part in spec.split(','):
        part = part.strip().lower()
        if not part:
            continue
        bar, exp = part.split(':')
        out.append((_to_secs(bar), _to_secs(exp)))
    return out


def _make_beep():
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
    try:
        ts = pd.to_datetime(candle_close_str)
        return (ts + pd.Timedelta(hours=tz_offset_hours)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(candle_close_str)


def alert_signal(d, channels='all', tz_offset=3):
    if d['action'] not in ('CALL', 'PUT'):
        return
    msg = (f'\n*** DOLPHIN TRADE SIGNAL ***\n'
           f'SYMBOL   : {d["symbol"]}\n'
           f'DIRECTION: {d["action"]} ({"UP" if d["action"] == "CALL" else "DOWN"})\n'
           f'ENTER NOW: within the next 60 seconds\n'
           f'TIMEFRAME: {d.get("tf", "-")} candles   EXPIRY: {d["expiry"]}\n'
           f'STAKE    : ${d["stake"]:.2f}\n'
           f'P        : {d["best_prob"]:.3f} (gate {d.get("gate", 0.65)})\n'
           f'EV       : {d["ev_score"]:+.3f}\n'
           f'CANDLE   : {d["candle_close"]} UTC  ({_fmt_server_time(d["candle_close"], tz_offset)} server+{tz_offset})\n'
           f'CANDLE O : {d.get("candle_open", "-")}   H: {d.get("candle_high", "-")}\n'
           f'CANDLE L : {d.get("candle_low", "-")}    C: {d.get("candle_close_price", "-")}\n'
           f'ENTRY    : {d.get("entry_price", "-")}   ATR: {d.get("atr", "-")}\n'
           f'TARGET   : {d.get("target_price", "-")}  (1x ATR)\n'
           f'STOP     : {d.get("stop_loss", "-")}  (invalidation 0.5x ATR)')
    news_line = []
    if d.get('sentiment_bias') and d['sentiment_bias'] != 'neutral':
        news_line.append(f"sentiment {d['sentiment_bias']}")
    if d.get('manipulation_risk') and d['manipulation_risk'] != 'low':
        news_line.append(f"risk {d['manipulation_risk']}")
    if d.get('news_next'):
        news_line.append(f"veto {d['news_next']}")
    if news_line:
        msg += '\nAGENTS  : ' + ' | '.join(news_line)
    LOGGER.info(msg)
    try:
        if channels in ('all', 'notify') and shutil.which('notify-send'):
            subprocess.run(['notify-send', 'DOLPHIN TRADE SIGNAL',
                            f"{d['symbol']} {d['action']} {d['tf']} now - P={d['best_prob']}"],
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

    def get_candles(self, pairs, size=600):
        out = []
        for _, grp in self.data.groupby('symbol'):
            out.append(grp.tail(size))
        return pd.concat(out, ignore_index=True)


class OlympFeed:
    def __init__(self, pairs):
        from common.socketconnect.Olymptradeconnect import OlympTradeClient
        self.client = OlympTradeClient(group='demo')
        self.pairs = pairs

    def get_candles(self, pairs, size=600):
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

    def place_bet(self, symbol, direction, amount, duration):
        return self.client.get_bet(direction, symbol, amount=amount, duration=str(duration))


def run_once(feed, orchestrator, equity, combos, live=False, alert='all', tz_offset=3,
             candles=None, tracker=None):
    if candles is None:
        candles = feed.get_candles(WATCHLIST, FETCH_CANDLES)
    decisions = orchestrator.decide(candles, combos, equity=equity)
    if tracker is not None:
        try:
            for d in decisions:
                if d['action'] in ('CALL', 'PUT'):
                    tracker.record(d)
            tracker.settle(candles)
        except Exception as e:
            LOGGER.exception(f'trade tracker failed: {e}')

    header = not os.path.exists(LOG_PATH)
    rows = []
    fired = [d for d in decisions if d['action'] in ('CALL', 'PUT')]
    for d in decisions:
        LOGGER.info(f"{d['symbol']:10s} TF{d['tf']:>4s} EXP{d['expiry']:>4s}: "
                    f"{d['action']:7s} P={d['best_prob']}  ev={d['ev_score']}  ({d['rationale']})")
        try:
            import json as _json
            LOGGER.info('DECISION-JSON ' + _json.dumps(d))
        except Exception:
            pass
        rows.append({'ts': datetime.now(timezone.utc).isoformat(), **d})
        if live and d['action'] in ('CALL', 'PUT') and d['stake'] > 0:
            try:
                dur = int(d['expiry'].rstrip('m')) * 60
                resp = feed.place_bet(d['symbol'], 'up' if d['action'] == 'CALL' else 'down',
                                      amount=str(d['stake']), duration=dur)
                LOGGER.info(f"BET placed {d['symbol']} {d['action']} {d['tf']}/{d['expiry']} -> {resp}")
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
            if best['best_prob'] >= orchestrator.theta:
                LOGGER.info(f'no signal this cycle (closest: {best["symbol"]} TF{best["tf"]} '
                            f'P={best["best_prob"]:.3f} passed gate but blocked by EV={best["ev_score"]:+.3f} < 0)')
            else:
                LOGGER.info(f'no signal this cycle (closest: {best["symbol"]} '
                            f'TF{best["tf"]} P={best["best_prob"]:.3f}, need >= {orchestrator.theta})')
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
    ap.add_argument('--theta', type=float, default=0.65,
                    help='probability gate (default 0.65; window mode: 0.55-0.60)')
    ap.add_argument('--hours', default='all',
                    help='trade only inside this UTC hour window, e.g. 15-17 (window mode; '
                         'validated 78-86 pct win rate 15-17 UTC at theta 0.55-0.60); default all')
    ap.add_argument('--combos', default='5m:15m,5m:30m,5m:1h,15m:1h,30m:1h',
                    help='comma list of bar:expiry combos, e.g. 5m:15m,15m:1h')
    ap.add_argument('--news-events', default='',
                    help='CSV (date,time_utc,currency,impact,title) of high-impact events; '
                         'enables the News-Event Momentum channel (measurement mode, no auto-bets)')
    ap.add_argument('--news-mode', choices=['cont', 'fade'], default='cont',
                    help='event strategy: cont = trade WITH strong spikes (15m expiry); '
                         'fade = trade AGAINST strong spikes (1h expiry)')
    ap.add_argument('--pairs', default=','.join(WATCHLIST))
    ap.add_argument('--equity', type=float, default=1000.0)
    ap.add_argument('--csv-dir', default=os.path.join(CURR, 'common', 'MachineLearningModel', 'output', 'five_mins'))
    args = ap.parse_args()

    hour_lo, hour_hi = 0, 24
    if args.hours != 'all':
        try:
            lo, hi = args.hours.split('-')
            hour_lo, hour_hi = int(lo), int(hi)
        except Exception:
            LOGGER.error(f'bad --hours {args.hours!r}; expected e.g. 15-17')
            sys.exit(1)

    combos = parse_combos(args.combos)
    service = DecisionService(theta=args.theta)
    if args.feed == 'csv':
        feed = CSVFeed(args.csv_dir)
    else:
        feed = OlympFeed([p.strip() for p in args.pairs.split(',')])

    # ---- multi-agent pipeline (real-time news + market + risk) ----
    from agents import NewsAgent, HeadlineAgent, RiskAgent, OrchestratorAgent, MarketAgent
    news = NewsAgent()
    news.refresh(force=True)
    if args.news_events:
        from news_strategy import load_events_file
        file_events = load_events_file(args.news_events)
        news.events = [{'time': e['time'].to_pydatetime(), 'currency': e['currency'],
                        'impact': e['impact'], 'title': e['title'],
                        'forecast': None, 'previous': None} for e in file_events]
        LOGGER.info(f'news agent seeded from file: {len(file_events)} events')
    headlines = HeadlineAgent()
    pairs_clean = [p.strip() for p in args.pairs.split(',')]
    headlines.refresh(pairs=pairs_clean, force=True)
    risk = RiskAgent()
    orchestrator = OrchestratorAgent(MarketAgent(service), news, headlines, risk, theta=args.theta)
    from trade_tracker import TradeTracker
    tracker = TradeTracker()
    LOGGER.info(f'ORCHESTRATOR READY: market={len(service.combo_models)} combos, '
                f'news events={len(news.events)}, llm_sentiment={headlines.llm is not None}')
    # structured agent context for the monitor UI
    try:
        import json as _json
        sentiment_map = {p: headlines.bias('FX:' + p) for p in pairs_clean}
        upcoming = news.upcoming()
        nxt = upcoming[0] if upcoming else None
        LOGGER.info('AGENT-CONTEXT ' + _json.dumps({
            'sentiment': sentiment_map,
            'next_event': nxt['title'] if nxt else None,
            'next_event_time': str(nxt['time']) if nxt else None,
            'events_total': len(news.events),
        }))
    except Exception:
        pass

    def in_window():
        return hour_lo <= datetime.utcnow().hour < hour_hi

    if args.once:
        news.refresh()
        headlines.refresh(pairs=pairs_clean)
        run_once(feed, orchestrator, args.equity, combos,
                 live=args.live and args.feed == 'olymp', alert=args.alert, tz_offset=args.tz_offset,
                 tracker=tracker)
        return

    mode = f'WINDOW {args.hours} UTC' if args.hours != 'all' else 'ALL HOURS'
    LOGGER.info(f'live loop started ({args.feed}) [{mode}] theta={args.theta} combos={args.combos}')
    last_decided = {}
    window_logged = None
    while True:
        time.sleep(30)
        if not in_window():
            cur = datetime.utcnow().hour
            if cur != window_logged:
                LOGGER.info(f'outside trading window ({args.hours} UTC) - skipping until {hour_hi}:00 UTC')
                window_logged = cur
            continue
        window_logged = None
        now = time.time()
        try:
            news.refresh()
            headlines.refresh(pairs=pairs_clean)
            candles = feed.get_candles(WATCHLIST, FETCH_CANDLES)
            for bar_sec, expiry_sec in combos:
                boundary = (now // bar_sec) * bar_sec
                if last_decided.get((bar_sec, expiry_sec)) == boundary:
                    continue
                if now - boundary < LATENCY_SEC:
                    continue
                last_decided[(bar_sec, expiry_sec)] = boundary
                run_once(feed, orchestrator, args.equity, [(bar_sec, expiry_sec)],
                         live=args.live and args.feed == 'olymp',
                         alert=args.alert, tz_offset=args.tz_offset, candles=candles,
                         tracker=tracker)
        except Exception as e:
            LOGGER.exception(f'decision cycle failed: {e}')


if __name__ == '__main__':
    main()
