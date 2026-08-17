"""Risk guardrails: dry-run, daily limits, cooldowns, circuit breaker, kill-switch.

All limits are read from the DB settings so they can be changed live from
the UI or Telegram without a restart.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import persistence

LOGGER = logging.getLogger('dolphin')

KEY_LIMITS = 'risk_limits'
KEY_KILL = 'kill_switch'
KEY_DRIFT = 'drift_stats'
KEY_PEAK = 'equity_peak'
KEY_BENCHMARK = 'benchmark_stats'
KEY_DRIFT_ALERT = 'drift_alert'
KEY_COMBO_BENCHMARK = 'combo_benchmark'
KEY_DISABLED = 'disabled_combos'

DEFAULT_BENCHMARK = 0.65        # expected win rate before a backtest benchmark
DRIFT_ALERT_PTS = 5.0           # alert when rolling live WR < benchmark - 5 pts
DRIFT_MIN_TRADES = 20           # min settled trades before judging
DRIFT_ALERT_COOLDOWN_H = 6.0    # don't re-alert more than once per 6h
COMBO_DRIFT_PTS = 5.0           # per-combo disable threshold (pts below bench)
COMBO_MIN_TRADES = 20           # min settled trades per combo before judging
COMBO_RE_EVALUATE_H = 24.0      # auto re-enable window for a disabled combo


def default_limits():
    return {
        'trade_mode': 'dry',       # live | dry (record only) | shadow (paper ledger)
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
        # trade_mode (explicitly stored) drives dry_run; legacy configs that
        # only set dry_run keep their own behaviour
        if 'trade_mode' in limits:
            merged['dry_run'] = limits['trade_mode'] != 'live'
    return merged


async def set_limits(session: AsyncSession, limits: dict):
    await persistence.set_setting(session, KEY_LIMITS, limits)
    return limits


async def kill_switch(session: AsyncSession) -> bool:
    return bool(await persistence.get_setting(session, KEY_KILL, False))


async def set_kill_switch(session: AsyncSession, on: bool):
    await persistence.set_setting(session, KEY_KILL, on)
    return on


async def allowed(session: AsyncSession, symbol: str, combo_key: str | None = None,
                  order_type: str | None = None) -> tuple[bool, str]:
    """Check every guardrail for a potential new trade."""
    if await kill_switch(session):
        return False, 'kill-switch is ON'
    limits = await get_limits(session)
    if limits.get('dry_run'):
        return False, 'dry-run mode'
    if combo_key and combo_key in (await disabled_combos(session)):
        return False, f'combo {combo_key} disabled by drift monitor'
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
    # per-symbol cooldown (only counts trades that actually placed)
    cooldown = limits.get('symbol_cooldown_min', 30)
    recent = await persistence.last_trades(session, n=200)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown)
    for t in recent:
        if t.status == 'cancelled':
            continue
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
    benchmark = await get_benchmark(session)
    projected = benchmark.get('win_rate', DEFAULT_BENCHMARK)
    stats = await persistence.get_setting(session, KEY_DRIFT, {})
    trades = await persistence.last_trades(session, n=300)
    settled = [t for t in trades if t.result in ('WIN', 'LOSS')]
    if len(settled) < 20:
        return {'sample': len(settled), 'paused': False, 'win_rate': None,
                'projected': projected, 'benchmark_source': benchmark.get('source'),
                'status': 'collecting'}
    wins = sum(1 for t in settled if t.result == 'WIN')
    win_rate = wins / len(settled)
    drift = projected - win_rate
    paused = drift >= 4.0 and len(settled) >= 50
    return {'sample': len(settled), 'paused': paused, 'win_rate': round(win_rate, 3),
            'projected': projected, 'benchmark_source': benchmark.get('source'),
            'drift_pts': round(drift * 100, 1), 'status': 'paused' if paused else 'ok'}


async def get_benchmark(session: AsyncSession) -> dict:
    """Expected win rate to compare live performance against (set from a
    backtest run). Falls back to the calibrated default."""
    b = await persistence.get_setting(session, KEY_BENCHMARK, {})
    if isinstance(b, dict) and b.get('win_rate'):
        return {'win_rate': float(b['win_rate']), 'source': b.get('source', 'backtest'),
                'ts': b.get('ts'), 'trades': b.get('trades')}
    return {'win_rate': DEFAULT_BENCHMARK, 'source': 'default', 'ts': None, 'trades': 0}


async def set_benchmark(session: AsyncSession, win_rate: float, source: str,
                        trades: int = 0):
    await persistence.set_setting(session, KEY_BENCHMARK, {
        'win_rate': round(float(win_rate), 4), 'source': source,
        'ts': str(datetime.now(timezone.utc)), 'trades': int(trades)})


async def save_combo_benchmark(session: AsyncSession, by_combo: dict):
    """Persist per-combo win rates from a backtest (keys like '5m->15m')."""
    out = {}
    for key, g in (by_combo or {}).items():
        wr = g.get('win_rate')
        if wr is not None and g.get('settled', 0) >= 10:
            out[key] = {'win_rate': round(float(wr), 4), 'trades': g['settled']}
    if out:
        await persistence.set_setting(session, KEY_COMBO_BENCHMARK, out)
    return out


def combo_key(d: dict) -> str:
    return f"{d.get('tf', '5m')}->{d.get('expiry', '15m')}"


async def disabled_combos(session: AsyncSession) -> dict:
    d = await persistence.get_setting(session, KEY_DISABLED, {})
    return d if isinstance(d, dict) else {}


async def is_combo_disabled(session: AsyncSession, key: str) -> bool:
    return key in (await disabled_combos(session))


async def enable_combo(session: AsyncSession, key: str) -> bool:
    d = await disabled_combos(session)
    if key in d:
        d.pop(key)
        await persistence.set_setting(session, KEY_DISABLED, d)
        return True
    return False


async def per_combo_drift(session: AsyncSession) -> dict:
    """Rolling live win rate per combo vs the backtest benchmark.

    Returns {combo_key: {sample, win_rate, benchmark, drift_pts, status}} for
    every combo with a stored benchmark that also has settled live trades.
    """
    bench = await persistence.get_setting(session, KEY_COMBO_BENCHMARK, {})
    if not isinstance(bench, dict) or not bench:
        return {}
    trades = await persistence.last_trades(session, n=500)
    grouped: dict[str, list] = {}
    for t in trades:
        if t.result not in ('WIN', 'LOSS'):
            continue
        key = f"{t.tf or '5m'}->{t.expiry or '15m'}"
        grouped.setdefault(key, []).append(t)
    out = {}
    for key, b in bench.items():
        rows = grouped.get(key, [])
        if len(rows) < 10:
            continue
        wins = sum(1 for t in rows if t.result == 'WIN')
        live_wr = wins / len(rows)
        benchmark_wr = float(b['win_rate'])
        out[key] = {
            'sample': len(rows),
            'win_rate': round(live_wr, 4),
            'benchmark': benchmark_wr,
            'drift_pts': round((benchmark_wr - live_wr) * 100, 1),
            'status': 'disabled' if key in (await disabled_combos(session))
            else ('ok' if live_wr >= benchmark_wr - COMBO_DRIFT_PTS / 100.0 else 'below'),
        }
    return out


async def _evaluate_disabled(session: AsyncSession) -> list[dict]:
    """Disable combos whose live win rate has stayed below their benchmark by
    COMBO_DRIFT_PTS over >= COMBO_MIN_TRADES settled trades; re-enable combos
    whose disable window has passed or that have recovered."""
    disabled = await disabled_combos(session)
    bench = await persistence.get_setting(session, KEY_COMBO_BENCHMARK, {})
    now = time.time()
    newly_disabled = []
    for key, b in (bench or {}).items():
        bwr = float(b['win_rate'])
        trades = [t for t in await persistence.last_trades(session, n=500)
                  if t.result in ('WIN', 'LOSS')
                  and f"{t.tf or '5m'}->{t.expiry or '15m'}" == key]
        if len(trades) < COMBO_MIN_TRADES:
            continue
        live_wr = sum(1 for t in trades if t.result == 'WIN') / len(trades)
        threshold = bwr - COMBO_DRIFT_PTS / 100.0
        if key in disabled:
            # re-enable if recovered or past the re-evaluation window
            if live_wr >= threshold or now - float(disabled[key].get('disabled_at', 0)) \
                    >= COMBO_RE_EVALUATE_H * 3600:
                disabled.pop(key)
            continue
        if live_wr < threshold:
            disabled[key] = {
                'disabled_at': now, 'reason': 'below benchmark',
                'benchmark': bwr, 'live_wr': round(live_wr, 4),
                'drift_pts': round((bwr - live_wr) * 100, 1)}
            newly_disabled.append(key)
    if disabled:
        await persistence.set_setting(session, KEY_DISABLED, disabled)
    else:
        await persistence.set_setting(session, KEY_DISABLED, {})
    return [{'combo': k, **disabled[k]} for k in newly_disabled]


async def drift_monitor(session: AsyncSession) -> dict:
    """Hourly drift check: compare the rolling live win rate against the
    benchmark, and auto-disable combos that stay below their per-combo
    benchmark. Returns the state; the caller sends alerts + records events."""
    state = await circuit_breaker_status(session)
    state['alert'] = False
    state['combo_disables'] = await _evaluate_disabled(session)
    state['disabled_combos'] = await disabled_combos(session)
    if state.get('win_rate') is None:
        return state
    sample = state['sample']
    benchmark = state['projected']
    if sample < DRIFT_MIN_TRADES:
        return state
    threshold = benchmark - DRIFT_ALERT_PTS / 100.0
    if state['win_rate'] >= threshold:
        return state
    # below threshold: respect the alert cooldown (don't spam Telegram)
    last = await persistence.get_setting(session, KEY_DRIFT_ALERT, 0.0)
    if time.time() - float(last or 0) < DRIFT_ALERT_COOLDOWN_H * 3600:
        state['alert'] = True          # still in breach, but already alerted
        state['alerted'] = True
        return state
    await persistence.set_setting(session, KEY_DRIFT_ALERT, time.time())
    state['alert'] = True
    state['alerted'] = True
    state['threshold'] = round(threshold, 3)
    return state
