"""Risk guardrails: dry-run, daily limits, cooldowns, circuit breaker, kill-switch.

All limits are read from the DB settings so they can be changed live from
the UI or Telegram without a restart.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import persistence

LOGGER = logging.getLogger('dolphin')

KEY_LIMITS = 'risk_limits'
KEY_KILL = 'kill_switch'
KEY_DRIFT = 'drift_stats'
KEY_PEAK = 'equity_peak'


def default_limits():
    return {
        'dry_run': True,
        'max_trades_per_day': 14,
        'max_daily_loss_pct': 5.0,
        'symbol_cooldown_min': 30,
        'stake_pct': 0.01,
        'equity': 1000.0,
        'order_types': ['binary', 'multiplier'],   # both markets per signal
        'multiplicator': 100,
        'sl_tp_mode': 'signal_levels',   # signal_levels | atr (multiplier only)
        'atr_sl_mult': 1.5,          # SL distance in ATRs for atr mode
        'atr_tp_mult': 3.0,          # TP distance in ATRs for atr mode
        'hourly_floor': 0.58,        # primary min best_prob for the hourly pick
        'hourly_floor_min': 0.55,    # fallback tier (still EV-positive per calib)
        'hw_stop_pct': 15.0,         # equity high-watermark stop (0 = off)
        'daily_profit_target_pct': 10.0,   # tiered basket profit target (0 = off)
        'loss_streak_reduce_after': 3,     # reduce stake after N consecutive losses
        'loss_streak_stake_factor': 0.5,   # stake multiplier per extra loss
        'news_blackout_min': 0,      # veto medium+high news within N min (0 = off)
    }


def normalize_order_types(limits: dict) -> list[str]:
    """order_types as a list; accepts legacy single-value order_type too."""
    ot = limits.get('order_types')
    if isinstance(ot, str):
        ot = [x.strip() for x in ot.split(',') if x.strip()]
    elif not isinstance(ot, list):
        legacy = limits.get('order_type', 'binary')
        ot = [legacy] if isinstance(legacy, str) else ['binary']
    return [m for m in ot if m in ('binary', 'multiplier')] or ['binary']


async def get_limits(session: AsyncSession) -> dict:
    limits = await persistence.get_setting(session, KEY_LIMITS)
    merged = default_limits()
    if isinstance(limits, dict):
        merged.update(limits)
        # legacy single-mode config ('order_type') wins until 'order_types'
        # is explicitly stored
        if 'order_types' not in limits and limits.get('order_type'):
            merged['order_types'] = [limits['order_type']]
    return merged


async def set_limits(session: AsyncSession, limits: dict):
    await persistence.set_setting(session, KEY_LIMITS, limits)
    return limits


async def kill_switch(session: AsyncSession) -> bool:
    return bool(await persistence.get_setting(session, KEY_KILL, False))


async def set_kill_switch(session: AsyncSession, on: bool):
    await persistence.set_setting(session, KEY_KILL, on)
    return on


async def allowed(session: AsyncSession, symbol: str) -> tuple[bool, str]:
    """Check every guardrail for a potential new trade."""
    if await kill_switch(session):
        return False, 'kill-switch is ON'
    limits = await get_limits(session)
    if limits.get('dry_run'):
        return False, 'dry-run mode'
    trades = await persistence.trades_today(session)
    if trades >= limits.get('max_trades_per_day', 10):
        return False, f'daily trade limit reached ({trades})'
    losses = await persistence.losses_today(session)
    equity = limits.get('equity', 1000.0)
    if equity and losses >= equity * limits.get('max_daily_loss_pct', 5.0) / 100.0:
        return False, f'daily loss limit reached (${losses:.2f})'
    # equity high-watermark stop (EA - Budak Ubat idea): block new entries
    # while equity sits below (100 - hw)% of the session peak
    pnl = await persistence.net_pnl_today(session)
    equity_now = equity + pnl
    peak = float(await persistence.get_setting(session, KEY_PEAK, 0.0) or 0.0)
    hw_pct = limits.get('hw_stop_pct', 0.0)
    if equity_now > peak:
        await persistence.set_setting(session, KEY_PEAK, equity_now)
        peak = equity_now
    if hw_pct and peak > 0 and equity_now < peak * (1.0 - hw_pct / 100.0):
        return False, (f'high-watermark stop (equity ${equity_now:.2f} < '
                       f'{hw_pct:.0f}% below peak ${peak:.2f})')
    # tiered daily profit target: close the day when net pnl reaches a target
    # that scales with how many trades the bot has taken today
    target_pct = limits.get('daily_profit_target_pct', 0.0)
    if target_pct and pnl > 0:
        tier = 1.0 + 0.25 * min(trades, 8)
        target = equity * target_pct / 100.0 * tier
        if pnl >= target:
            return False, f'profit target reached (${pnl:.2f} >= ${target:.2f})'
    # per-symbol cooldown
    cooldown = limits.get('symbol_cooldown_min', 30)
    recent = await persistence.last_trades(session, n=200)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown)
    for t in recent:
        if t.symbol == symbol and t.ts and t.ts.replace(tzinfo=timezone.utc) >= cutoff:
            return False, f'{symbol} in cooldown ({cooldown} min)'
    return True, 'ok'


async def loss_streak(session: AsyncSession, max_scan: int = 50) -> int:
    """Consecutive LOSS results ending at the most recent settled trade."""
    trades = await persistence.last_trades(session, n=max_scan)
    streak = 0
    for t in trades:
        if t.result == 'LOSS':
            streak += 1
        elif t.result == 'WIN':
            break
        else:
            continue          # draws/open skipped
    return streak


async def stake_for(session: AsyncSession, base_stake: float, limits: dict) -> float:
    """Loss-streak stake reduction (EA AutoMarti DecreaseFactor idea)."""
    factor = limits.get('loss_streak_stake_factor', 0.5)
    after = limits.get('loss_streak_reduce_after', 0)
    if not factor or not after:
        return base_stake
    streak = await loss_streak(session)
    if streak < after:
        return base_stake
    mult = factor ** min(streak - after + 1, 3)
    return round(base_stake * mult, 2)


async def circuit_breaker_status(session: AsyncSession) -> dict:
    """Realized-vs-projected drift over the last N settled trades."""
    stats = await persistence.get_setting(session, KEY_DRIFT, {})
    trades = await persistence.last_trades(session, n=300)
    settled = [t for t in trades if t.result in ('WIN', 'LOSS')]
    if len(settled) < 20:
        return {'sample': len(settled), 'paused': False, 'win_rate': None,
                'projected': None, 'status': 'collecting'}
    wins = sum(1 for t in settled if t.result == 'WIN')
    win_rate = wins / len(settled)
    projected = 0.65 if not stats else stats.get('projected', 0.65)
    drift = projected - win_rate
    paused = drift >= 4.0 and len(settled) >= 50
    return {'sample': len(settled), 'paused': paused, 'win_rate': round(win_rate, 3),
            'projected': projected, 'drift_pts': round(drift * 100, 1), 'status': 'paused' if paused else 'ok'}
