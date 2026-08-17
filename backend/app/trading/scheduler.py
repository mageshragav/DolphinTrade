"""Boundary scheduler: runs the trading cycle at every combo's bar close.

Aligned to epoch boundaries (no cron drift). Waits LATENCY_SEC after a
boundary so the candle is settled, then fetches the 5m native feed once and
drives the runtime. Respects the UTC hours window and the kill-switch.
"""

import asyncio
import subprocess
import logging
import time
from datetime import datetime, timezone

from app import ws
from app.config import get_settings
from app.db import SessionLocal
from app.services import risk as risk_svc

LOGGER = logging.getLogger('dolphin')

LATENCY_SEC = 30
TICK_SEC = 20


def parse_combos(spec: str):
    out = []
    for part in spec.split(','):
        part = part.strip().lower()
        if not part:
            continue
        bar, exp = part.split(':')
        bar_s = int(bar.rstrip('m')) * 60 if bar.endswith('m') else int(bar.rstrip('h')) * 3600
        exp_s = int(exp.rstrip('m')) * 60 if exp.endswith('m') else int(exp.rstrip('h')) * 3600
        out.append((bar_s, exp_s))
    return out


def in_window(hours: str, now: datetime) -> bool:
    if hours in ('', 'all'):
        return True
    try:
        lo, hi = hours.split('-')
        return int(lo) <= now.hour < int(hi)
    except Exception:
        return True


class Scheduler:
    def __init__(self, runtime, feed):
        self.runtime = runtime
        self.feed = feed
        self.last_decided = {}
        self.running = False
        self._token_warned = set()          # thresholds already alerted
        self._scan_hour = None              # last UTC hour the guarantee ran
        self._last_refresh_attempt = 0.0    # epoch of last auto-refresh launch

    async def _auto_refresh_token(self, force=False):
        """Launch the headless auto-login (fire and forget) when the session
        token is within AUTO_REFRESH_HOURS of expiry or already expired."""
        import os as _os
        import sys as _sys
        from app.runtime_ctx import RUNTIME
        now = time.time()
        if now - self._last_refresh_attempt < 6 * 3600 and not force:
            return False                       # at most ~once per 6h
        script = _os.path.join(_os.path.dirname(_os.path.dirname(
            _os.path.dirname(_os.path.abspath(__file__)))), 'scripts', 'refresh_token.py')
        if not _os.path.exists(script):
            return False
        api = _os.environ.get('DT_PUBLIC_URL', 'http://127.0.0.1:8000')
        self._last_refresh_attempt = now
        env = dict(_os.environ)
        try:
            proc = subprocess.Popen(
                [_sys.executable, script, '--push', api],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                cwd=_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
                env=env)
        except Exception as e:
            LOGGER.warning(f'auto token refresh launch failed: {e}')
            return False
        LOGGER.info(f'auto token refresh triggered (pid {proc.pid}, api {api})')
        bot = RUNTIME.get('telegram')
        if bot:
            try:
                bot.send('🔄 Session token expiring - auto-refresh started '
                         '(headless login). Will hot-swap when it succeeds.')
            except Exception:
                pass
        return True

    async def _check_token_health(self):
        """Warn once per threshold as the session token nears expiry; trigger
        the auto-login before it dies."""
        from app.connectors.olymp import token_expiry, token_ok
        from app.runtime_ctx import RUNTIME
        exp = token_expiry()
        if exp is None:
            if 'missing' not in self._token_warned:
                self._token_warned.add('missing')
                bot = RUNTIME.get('telegram')
                msg = ('OLYMP SESSION TOKEN MISSING/INVALID - order placement '
                       'will fail. Auto-refresh attempted; fallback: /token <jwt>')
                LOGGER.error(msg)
                await self._auto_refresh_token(force=True)
                if bot:
                    try:
                        bot.send(msg)
                    except Exception:
                        pass
            return
        left_h = (exp - datetime.now(timezone.utc)).total_seconds() / 3600.0
        if left_h <= 12.0:
            await self._auto_refresh_token()
        for threshold, label in ((6.0, '6h'), (2.0, '2h'), (0.5, '30min')):
            if left_h <= threshold and f'{threshold}' not in self._token_warned:
                self._token_warned.add(f'{threshold}')
                bot = RUNTIME.get('telegram')
                msg = (f'OLYMP SESSION TOKEN expires in ~{label} '
                       f'({exp:%Y-%m-%d %H:%M} UTC). Renew now: /token <jwt>')
                LOGGER.warning(msg)
                if bot:
                    try:
                        bot.send(msg)
                    except Exception:
                        pass

    async def run(self):
        self.running = True
        settings = get_settings()
        combos = parse_combos(settings.combos)
        pairs = [p.strip() for p in settings.pairs.split(',') if p.strip()]
        LOGGER.info(f'scheduler started: {len(combos)} combos, window={settings.hours_window}')
        while self.running:
            await asyncio.sleep(TICK_SEC)
            now = time.time()
            # session-token watchdog (cheap: local JWT decode every 5 min)
            if int(now) % 300 < TICK_SEC:
                try:
                    await self._check_token_health()
                except Exception as e:
                    LOGGER.debug(f'token health check failed: {e}')
            # hourly minimum-signal guarantee: once per hour at :minute, if
            # the hour has no trade, pick the best candidate above the floor
            hh = datetime.now(timezone.utc)
            if settings.hourly_guarantee and self._scan_hour != hh.strftime('%Y%m%d%H') \
                    and hh.minute >= settings.hourly_minute:
                self._scan_hour = hh.strftime('%Y%m%d%H')
                try:
                    candles = await self.runtime.fetch_candles(self.feed)
                    if candles is not None and not candles.empty:
                        await self.runtime.hourly_scan(candles)
                except Exception as e:
                    LOGGER.exception(f'hourly guarantee scan failed: {e}')

            if not in_window(settings.hours_window, datetime.now(timezone.utc)):
                continue
            # kill switch pauses trading (decisions still stream)
            async with SessionLocal() as session:
                killed = await risk_svc.kill_switch(session)
            try:
                await self.runtime.refresh_agents(pairs)
                candles = await self.runtime.fetch_candles(self.feed)
                due = []
                for bar_sec, exp_sec in combos:
                    boundary = (now // bar_sec) * bar_sec
                    key = (bar_sec, exp_sec)
                    if self.last_decided.get(key) == boundary:
                        continue
                    if now - boundary < LATENCY_SEC:
                        continue
                    self.last_decided[key] = boundary
                    due.append((bar_sec, exp_sec))
                if not due:
                    continue
                if killed:
                    LOGGER.info('kill-switch ON - decisions logged, no trades')
                history = None
                if hasattr(self.feed, 'history'):
                    history = await asyncio.to_thread(self.feed.history)
                await self.runtime.cycle(candles, history=history)
            except Exception as e:
                LOGGER.exception(f'scheduler cycle failed: {e}')

    def stop(self):
        self.running = False
