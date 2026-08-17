"""Telegram bot: signal forwarding + operator commands.

Runs polling in a background thread. Commands:
  /status   - monitor state, limits, circuit breaker
  /trades   - last 5 trades with results
  /stop     - kill switch ON
  /start    - kill switch OFF
  /limits   - current risk limits
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone

from app.config import get_settings
from app.db import SessionLocal
from app.services import persistence, risk as risk_svc
from app.runtime_ctx import RUNTIME

LOGGER = logging.getLogger('dolphin')


class TelegramBot:
    def __init__(self, token: str = None, group_id: str = None):
        settings = get_settings()
        self.token = token or settings.telegram_bot_token
        self.group_id = str(group_id or settings.telegram_group_id)
        self.bot = None
        self.thread = None
        self.running = False
        self.lock_path = None

    def _acquire_lock(self) -> bool:
        """Cross-process singleton: only one poller per token.

        Stale locks (owner PID no longer alive) are reclaimed automatically so
        a killed instance never disables telegram for the replacement.
        """
        import hashlib
        lock_name = f'/tmp/dolphin_telegram_{hashlib.md5(self.token.encode()).hexdigest()[:12]}.lock'
        for attempt in range(2):
            try:
                fd = os.open(lock_name, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self.lock_path = lock_name
                return True
            except FileExistsError:
                try:
                    with open(lock_name) as f:
                        owner = int(f.read().strip() or 0)
                except Exception:
                    owner = -1
                alive = False
                if owner > 0:
                    try:
                        os.kill(owner, 0)
                        alive = True
                    except OSError:
                        alive = False
                if alive or attempt > 0:
                    return False
                try:
                    os.remove(lock_name)          # stale lock: owner is dead
                except OSError:
                    return False
        return False

    def _release_lock(self):
        if self.lock_path and os.path.exists(self.lock_path):
            try:
                os.remove(self.lock_path)
            except Exception:
                pass
            self.lock_path = None

    def start(self):
        if not self.token:
            LOGGER.warning('telegram disabled: no token configured')
            return
        if not self._acquire_lock():
            LOGGER.warning('telegram disabled: another process is already polling '
                           'with this token (kill the duplicate server first)')
            return
        try:
            import telebot
            self.bot = telebot.TeleBot(self.token, threaded=True)
            self._register_handlers()
            self.thread = threading.Thread(target=self._poll_loop, daemon=True)
            self.thread.start()
            self.running = True
            LOGGER.info('telegram bot started (singleton lock acquired)')
        except Exception as e:
            LOGGER.warning(f'telegram start failed: {e}')
            self._release_lock()

    def stop(self):
        self.running = False
        if self.bot:
            try:
                self.bot.stop_polling()
            except Exception:
                pass
        self._release_lock()

    def _poll_loop(self):
        """Resilient polling: never crashes on API errors, respects the lock."""
        while True:
            if not self.running:
                return
            try:
                self.bot.infinity_polling(timeout=20, long_polling_timeout=20)
                return
            except Exception as e:
                msg = str(e)
                if '409' in msg or 'Conflict' in msg:
                    LOGGER.warning('telegram conflict: another instance is polling - '
                                   'stopping this one')
                    self.running = False
                    self._release_lock()
                    return
                LOGGER.warning(f'telegram polling error ({type(e).__name__}): {msg[:120]} '
                               '- retrying in 15s')
                time.sleep(15)

    def _register_handlers(self):
        @self.bot.message_handler(commands=['status'])
        def on_status(msg):
            try:
                self._send_reply(msg, self._status_text())
            except Exception as e:
                LOGGER.warning(f'status reply failed: {e}')

        @self.bot.message_handler(commands=['trades'])
        def on_trades(msg):
            self._send_reply(msg, self._trades_text())

        @self.bot.message_handler(commands=['stop'])
        def on_stop(msg):
            self._set_kill(True)
            self._send_reply(msg, 'KILL SWITCH ON - no new trades will be placed.')

        @self.bot.message_handler(commands=['start'])
        def on_start(msg):
            self._set_kill(False)
            self._send_reply(msg, 'KILL SWITCH OFF - trading resumed.')

        @self.bot.message_handler(commands=['limits'])
        def on_limits(msg):
            self._send_reply(msg, self._limits_text())

        @self.bot.message_handler(commands=['token'])
        def on_token(msg):
            """/token <jwt> - hot-swap the olymp session token (no restart)."""
            parts = (msg.text or '').split()
            if len(parts) < 2:
                from app.connectors.olymp import token_expiry
                exp = token_expiry()
                self._send_reply(msg, f'Usage: /token <access_token>'
                                      f'\nCurrent token valid until: {exp}')
                return
            import asyncio as _asyncio
            async def _swap():
                rt = RUNTIME.get('runtime')
                if rt is None or getattr(rt, 'connector', None) is None:
                    return 'connector not initialized'
                ok = rt.connector.set_token(parts[1].strip())
                return 'token updated and verified' if ok else 'token update FAILED'
            self._send_reply(msg, _asyncio.run(_swap()))

        @self.bot.message_handler(commands=['renew'])
        def on_renew(msg):
            """/renew - renew the session token via the refresh endpoint."""
            import asyncio as _asyncio
            from app.connectors.olymp import renew_session
            from app.runtime_ctx import RUNTIME
            async def _do():
                res = await _asyncio.to_thread(renew_session)
                if res.get('ok'):
                    rt = RUNTIME.get('runtime')
                    if rt is not None and getattr(rt, 'connector', None) is not None:
                        from common.constants import cookies
                        rt.connector.set_token(cookies['access_token'])
                    return f'Token renewed - valid until {res.get("expires_at")}'
                return f'Renew failed: {res.get("msg")}'
            self._send_reply(msg, _asyncio.run(_do()))

        @self.bot.message_handler(commands=['mode'])
        def on_mode(msg):
            """/mode - toggle which markets each signal trades (binary / multiplier)."""
            import asyncio as _asyncio
            parts = (msg.text or '').split()
            async def _toggle():
                async with SessionLocal() as session:
                    limits = await risk_svc.get_limits(session)
                    modes = risk_svc.normalize_order_types(limits)
                    if len(parts) >= 2 and parts[1].strip() in ('binary', 'multiplier'):
                        want = parts[1].strip()
                        modes = [m for m in modes if m != want]
                        if want not in modes:
                            modes.append(want)
                        if not modes:
                            modes = ['binary']
                        limits['order_types'] = modes
                        await risk_svc.set_limits(session, limits)
                        return f'Order markets: {", ".join(modes)}'
                    # no arg: cycle binary -> multiplier -> both -> binary
                    if modes == ['binary']:
                        limits['order_types'] = ['binary', 'multiplier']
                    elif modes == ['multiplier']:
                        limits['order_types'] = ['binary']
                    else:
                        limits['order_types'] = ['multiplier']
                    await risk_svc.set_limits(session, limits)
                    return f'Order markets: {", ".join(limits["order_types"])}'
            self._send_reply(msg, _asyncio.run(_toggle()))

    def _mode_text(self):
        import asyncio
        async def _do():
            async with SessionLocal() as session:
                limits = await risk_svc.get_limits(session)
            ot = limits.get('order_type', 'binary')
            return (f'Order mode: {ot}' +
                    (f' at {limits.get("multiplicator", 100)}x' if ot == 'multiplier' else '') +
                    '\nToggle with /mode')
        return asyncio.run(_do())

    def _send_reply(self, msg, text):
        self.bot.reply_to(msg, text)

    def _set_kill(self, on: bool):
        import asyncio
        async def _do():
            async with SessionLocal() as session:
                await risk_svc.set_kill_switch(session, on)
        asyncio.run(_do())

    def _status_text(self):
        import asyncio
        async def _do():
            async with SessionLocal() as session:
                limits = await risk_svc.get_limits(session)
                breaker = await risk_svc.circuit_breaker_status(session)
                trades = await persistence.trades_today(session)
                killed = await risk_svc.kill_switch(session)
            return (f'DolphinTrade status\n'
                    f'  kill-switch: {"ON" if killed else "off"}\n'
                    f'  dry-run: {"yes" if limits.get("dry_run") else "NO"}\n'
                    f'  trades today: {trades}/{limits.get("max_trades_per_day")}\n'
                    f'  circuit breaker: {breaker.get("status")} '
                    f'(win {breaker.get("win_rate")} vs proj {breaker.get("projected")})\n'
                    f'  stake: {limits.get("stake_pct")*100:.0f}%')
        return asyncio.run(_do())

    def _trades_text(self):
        import asyncio
        async def _do():
            async with SessionLocal() as session:
                trades = await persistence.last_trades(session, n=5)
            lines = ['Last 5 trades:']
            for t in trades:
                res = t.result or t.status
                lines.append(f'  {t.symbol} {t.action} {t.expiry} entry={t.entry} -> {res}')
            return '\n'.join(lines)
        return asyncio.run(_do())

    def _limits_text(self):
        import asyncio
        async def _do():
            async with SessionLocal() as session:
                limits = await risk_svc.get_limits(session)
            hw = limits.get('hw_stop_pct', 0.0)
            target = limits.get('daily_profit_target_pct', 0.0)
            streak_a = limits.get('loss_streak_reduce_after', 0)
            nb = limits.get('news_blackout_min', 0)
            return ('Risk limits:\n'
                    f'  dry_run: {limits.get("dry_run")}\n'
                    f'  max trades/day: {limits.get("max_trades_per_day")}\n'
                    f'  max daily loss: {limits.get("max_daily_loss_pct")}%\n'
                    f'  symbol cooldown: {limits.get("symbol_cooldown_min")} min\n'
                    f'  stake: {limits.get("stake_pct")*100:.0f}%\n'
                    f'  order mode: {", ".join(risk_svc.normalize_order_types(limits))}'
                    f'{" " + str(limits.get("multiplicator")) + "x" if "multiplier" in risk_svc.normalize_order_types(limits) else ""}'
                    f' (SL/TP: {limits.get("sl_tp_mode", "signal_levels")})\n'
                    f'  high-watermark stop: {hw:.0f}%\n'
                    f'  profit target: {target:.0f}%'
                    f'{" (tiered)" if target else ""}\n'
                    f'  loss-streak cut: after {streak_a} losses\n'
                    f'  news blackout: {nb} min')
        return asyncio.run(_do())

    def send(self, text: str):
        """Send a plain message to the configured group (used for alerts)."""
        if not self.token:
            return False
        try:
            import telebot
            bot = self.bot or telebot.TeleBot(self.token)
            bot.send_message(chat_id=self.group_id, text=text)
            return True
        except Exception as e:
            LOGGER.warning(f'alert send failed: {e}')
            return False

    def send_signal(self, d: dict):
        if not self.token:
            return
        try:
            import telebot
            # sending works even when this instance did not win the poll lock
            bot = self.bot or telebot.TeleBot(self.token)
            msg = (f'\U0001f40b SIGNAL {d.get("symbol")}\n'
                   f'{d.get("action")} ({d.get("expiry")})\n'
                   f'Entry {d.get("entry_price")} | Target {d.get("target_price")} '
                   f'| Stop {d.get("stop_loss")}\n'
                   f'P={d.get("best_prob")} EV={d.get("ev_score")}')
            bot.send_message(chat_id=self.group_id, text=msg)
            return True
        except Exception as e:
            LOGGER.warning(f'signal send failed: {e}')
            return False
