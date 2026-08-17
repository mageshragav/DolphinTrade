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
        self._last_drift_check = 0.0        # epoch of last drift monitor run
        self._last_report_day = ''         # last UTC day the daily report ran

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
        if not (_os.environ.get('DT_OLYMP_EMAIL') and _os.environ.get('DT_OLYMP_PASSWORD')):
            LOGGER.warning('auto token refresh skipped: DT_OLYMP_EMAIL/PASSWORD not set')
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
        """Renew the session before it dies (refresh-token endpoint), warn on
        thresholds, and fall back to headless login + manual paste."""
        from app.connectors.olymp import renew_session, token_expiry, token_ok
        from app.runtime_ctx import RUNTIME
        exp = token_expiry()
        now = datetime.now(timezone.utc)
        if exp is None:
            left_h = -1.0
        else:
            left_h = (exp - now).total_seconds() / 3600.0

        # primary path: refresh-token renew (no captcha) when close to expiry
        if left_h <= 12.0:
            res = await asyncio.to_thread(renew_session)
            if res.get('ok'):
                LOGGER.info(f'session token auto-renewed: {res.get("expires_at")}')
                bot = RUNTIME.get('telegram')
                if bot:
                    try:
                        bot.send(f'🔑 Session token auto-renewed - valid until '
                                 f'{res.get("expires_at")}')
                    except Exception:
                        pass
                rt = RUNTIME.get('runtime')
                if rt is not None and getattr(rt, 'connector', None) is not None:
                    try:
                        from app.connectors.olymp import token_expiry as te2
                        rt.connector.set_token(
                            __import__('common.constants', fromlist=['cookies'])
                            .cookies['access_token'])
                    except Exception as e:
                        LOGGER.warning(f'post-renew reconnect failed: {e}')
                return
            LOGGER.warning(f'auto renew failed ({res.get("msg")}) - '
                           f'falling back to headless login')

        # fallback: headless chrome login
        if left_h <= 12.0:
            await self._auto_refresh_token()

        if exp is None:
            if 'missing' not in self._token_warned:
                self._token_warned.add('missing')
                bot = RUNTIME.get('telegram')
                msg = ('OLYMP SESSION TOKEN MISSING/INVALID - order placement '
                       'will fail. Fallback: /token <jwt>')
                LOGGER.error(msg)
                if bot:
                    try:
                        bot.send(msg)
                    except Exception:
                        pass
            return
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

    async def _nightly_report(self):
        """Daily 00:05 UTC Telegram performance report (template-based)."""
        from app.runtime_ctx import RUNTIME
        from app.services import analytics
        from app.services import persistence
        async with SessionLocal() as session:
            a = await analytics.analytics(session)
            text = analytics.build_nightly_report(a)
            await persistence.record_agent_event(
                session, 'report', 'daily report generated', None,
                {'text': text})
        bot = RUNTIME.get('telegram')
        if bot:
            try:
                bot.send(text)
                return {'sent': True}
            except Exception as e:
                LOGGER.warning(f'daily report send failed: {e}')
        return {'sent': False}

    async def _check_drift(self):
        """Hourly drift check: rolling live win rate vs benchmark -> alert."""
        from app.runtime_ctx import RUNTIME
        from app.services import persistence
        async with SessionLocal() as session:
            state = await risk_svc.drift_monitor(session)
            if state.get('alert') and not state.get('alerted'):
                await persistence.record_agent_event(
                    session, 'drift', state['status'], None,
                    {'win_rate': state.get('win_rate'),
                     'benchmark': state.get('projected'),
                     'threshold': state.get('threshold')})
                await ws.broadcast({'type': 'alert',
                                    'message': f'DRIFT: live win rate '
                                               f'{state["win_rate"]} vs benchmark '
                                               f'{state["projected"]} (below '
                                               f'{state.get("threshold")})'})
        if state.get('alert') and not state.get('alerted'):
            bot = RUNTIME.get('telegram')
            if bot:
                try:
                    bot.send(f'⚠️ DRIFT ALERT: live win rate '
                             f'{state["win_rate"]} vs benchmark '
                             f'{state["projected"]} over {state["sample"]} trades - '
                             f'performance is degrading. Review settings or pause.')
                except Exception:
                    pass
            LOGGER.warning(f'drift alert: win_rate={state["win_rate"]} '
                           f'vs benchmark={state["projected"]}')
        return state

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
            # drift monitor (rolling live win rate vs benchmark) every hour
            if now - self._last_drift_check > 3600:
                self._last_drift_check = now
                try:
                    await self._check_drift()
                except Exception as e:
                    LOGGER.debug(f'drift check failed: {e}')
            # nightly performance report at 00:05 UTC
            if self._last_report_day != datetime.now(timezone.utc).strftime('%Y%m%d') \
                    and datetime.now(timezone.utc).minute >= 5 \
                    and datetime.now(timezone.utc).hour == 0:
                self._last_report_day = datetime.now(timezone.utc).strftime('%Y%m%d')
                try:
                    await self._nightly_report()
                except Exception as e:
                    LOGGER.warning(f'nightly report failed: {e}')
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
