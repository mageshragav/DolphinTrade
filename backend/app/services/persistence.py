"""Persistence helpers: decisions, trades, agent events, signals, settings, candles."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


async def add(obj, session: AsyncSession, commit=True):
    session.add(obj)
    if commit:
        await session.commit()
        await session.refresh(obj)
    return obj


async def record_decision(session: AsyncSession, d: dict) -> models.Decision:
    row = models.Decision(
        symbol=d.get('symbol', ''), tf=d.get('tf', '5m'), expiry=d.get('expiry', '15m'),
        action=d.get('action', 'NEUTRAL'), p_call=d.get('p_call', 0.0),
        p_put=d.get('p_put', 0.0), best_prob=d.get('best_prob', 0.0),
        ev_score=d.get('ev_score', 0.0), candle_close=d.get('candle_close', ''),
        candle_open=d.get('candle_open'), candle_high=d.get('candle_high'),
        candle_low=d.get('candle_low'), candle_close_price=d.get('candle_close_price'),
        entry_price=d.get('entry_price'), target_price=d.get('target_price'),
        stop_loss=d.get('stop_loss'), atr=d.get('atr'),
        sentiment_bias=d.get('sentiment_bias', 'neutral'),
        manipulation_risk=d.get('manipulation_risk', 'low'),
        news_veto=d.get('news_veto', False), news_next=d.get('news_next'),
        headline=d.get('headline'), model=d.get('model', ''),
        rationale=d.get('rationale', ''), payload=d)
    await add(row, session)
    return row


async def record_trade(session: AsyncSession, t: dict) -> models.Trade:
    row = models.Trade(
        decision_id=t.get('decision_id'), symbol=t.get('symbol', ''), tf=t.get('tf', '5m'),
        expiry=t.get('expiry', '15m'), action=t.get('action', 'CALL'),
        candle_open=t.get('candle_open'), candle_close=t.get('candle_close'),
        entry=t.get('entry'), take_profit=t.get('take_profit'), stop_loss=t.get('stop_loss'),
        expiry_time=t.get('expiry_time'), candle_close_ts=t.get('candle_close_ts'),
        status=t.get('status', 'open'),
        exit_price=t.get('exit_price'), result=t.get('result'),
        broker_ref=t.get('broker_ref'), broker_status=t.get('broker_status'),
        winperc=t.get('winperc'), order_type=t.get('order_type', 'binary'),
        placed_ts=t.get('placed_ts'),
        dry_run=t.get('dry_run', True), shadow=t.get('shadow', False),
        stake=t.get('stake', 0.0), reason=t.get('reason', ''))
    await add(row, session)
    return row


async def update_trade(session: AsyncSession, trade_id: int, **fields):
    row = await session.get(models.Trade, trade_id)
    if row is None:
        return None
    for k, v in fields.items():
        setattr(row, k, v)
    await session.commit()
    return row


async def record_agent_event(session: AsyncSession, kind, summary, symbol=None, payload=None):
    row = models.AgentEvent(kind=kind, summary=summary, symbol=symbol, payload=payload)
    await add(row, session)
    return row


async def record_signal(session: AsyncSession, d: dict) -> models.Signal:
    row = models.Signal(symbol=d.get('symbol', ''), expiry=d.get('expiry', '15m'),
                        action=d.get('action', 'CALL'), payload=d)
    await add(row, session)
    return row


async def get_setting(session: AsyncSession, key: str, default=None):
    row = await session.get(models.BotSetting, key)
    return row.value if row is not None else default


async def set_setting(session: AsyncSession, key: str, value):
    row = await session.get(models.BotSetting, key)
    if row is None:
        row = models.BotSetting(key=key, value=value)
        session.add(row)
    else:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return value


async def trades_today(session: AsyncSession) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    q = select(func.count(models.Trade.id)).where(
        models.Trade.ts >= start,
        models.Trade.dry_run.is_(False))
    return (await session.execute(q)).scalar() or 0


async def open_trades_count(session: AsyncSession) -> int:
    """Currently open (unsettled) trades across all symbols/markets."""
    q = select(func.count(models.Trade.id)).where(models.Trade.status == 'open')
    return (await session.execute(q)).scalar() or 0


async def inflight_stake(session: AsyncSession) -> float:
    """Total stake currently committed to open trades."""
    q = select(func.coalesce(func.sum(models.Trade.stake), 0.0)).where(
        models.Trade.status == 'open')
    return float((await session.execute(q)).scalar() or 0.0)


async def trades_in_hour(session: AsyncSession, hour_key: str) -> int:
    """Non-cancelled trades whose UTC hour matches 'YYYYMMDDHH'."""
    try:
        h = datetime.strptime(hour_key, '%Y%m%d%H').replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    q = select(func.count(models.Trade.id)).where(
        models.Trade.ts >= h,
        models.Trade.ts < h + timedelta(hours=1),
        models.Trade.status != 'cancelled')
    return (await session.execute(q)).scalar() or 0


async def losses_today(session: AsyncSession) -> float:
    """Sum of stakes lost today on real trades (settled LOSS)."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    q = select(models.Trade).where(
        models.Trade.ts >= start,
        models.Trade.dry_run.is_(False),
        models.Trade.result == 'LOSS')
    rows = (await session.execute(q)).scalars().all()
    return sum(r.stake or 0 for r in rows)


async def net_pnl_today(session: AsyncSession) -> float:
    """Realized net PnL today: stake * winperc/100 on WIN, -stake on LOSS."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    q = select(models.Trade).where(
        models.Trade.ts >= start,
        models.Trade.dry_run.is_(False),
        models.Trade.result.in_(('WIN', 'LOSS')))
    rows = (await session.execute(q)).scalars().all()
    pnl = 0.0
    for r in rows:
        stake = r.stake or 0.0
        if r.result == 'WIN':
            pnl += stake * (r.winperc or 0.0) / 100.0
        else:
            pnl -= stake
    return round(pnl, 4)


async def last_trades(session: AsyncSession, n: int = 30) -> list[models.Trade]:
    q = select(models.Trade).order_by(models.Trade.id.desc()).limit(n)
    return list((await session.execute(q)).scalars().all())


async def last_decisions(session: AsyncSession, n: int = 100) -> list[models.Decision]:
    q = select(models.Decision).order_by(models.Decision.id.desc()).limit(n)
    return list((await session.execute(q)).scalars().all())


async def recent_signals(session: AsyncSession, n: int = 30) -> list[models.Signal]:
    q = select(models.Signal).order_by(models.Signal.id.desc()).limit(n)
    return list((await session.execute(q)).scalars().all())


async def recent_agent_events(session: AsyncSession, n: int = 50) -> list[models.AgentEvent]:
    q = select(models.AgentEvent).order_by(models.AgentEvent.id.desc()).limit(n)
    return list((await session.execute(q)).scalars().all())


async def trade_exists(session: AsyncSession, symbol: str, candle_close: str, action: str,
                       expiry: str, order_type: str = 'binary') -> bool:
    if not candle_close:
        return False
    # exact signal identity: same candle close time + direction + expiry +
    # market; cancelled trades never placed, so they don't count
    q = select(models.Trade.id).where(
        models.Trade.symbol == symbol,
        models.Trade.action == action,
        models.Trade.expiry == expiry,
        models.Trade.candle_close_ts == candle_close,
        models.Trade.order_type == order_type,
        models.Trade.status != 'cancelled')
    rows = (await session.execute(q)).scalars().all()
    if rows:
        return True
    # fallback: expiry-time window for legacy rows without candle_close_ts
    try:
        ts = datetime.fromisoformat(candle_close)
        if expiry.endswith('h'):
            exp_ts = ts + timedelta(hours=int(expiry[:-1]))
        else:
            exp_ts = ts + timedelta(minutes=int(expiry.rstrip('m')))
    except Exception:
        return False
    q = select(models.Trade.id).where(
        models.Trade.symbol == symbol,
        models.Trade.action == action,
        models.Trade.expiry == expiry,
        models.Trade.expiry_time >= exp_ts - timedelta(hours=2),
        models.Trade.expiry_time <= exp_ts + timedelta(hours=2),
        models.Trade.status != 'cancelled')
    rows = (await session.execute(q)).scalars().all()
    return len(rows) > 0


# ---------------------------------------------------------------------------
# candle archive (OHLCV history for backtests / analytics)
# ---------------------------------------------------------------------------

def _candle_field(row, short, long_, default=None):
    v = row.get(short)
    if v is None:
        v = row.get(long_)
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


async def archive_candles(session: AsyncSession, df, interval: int = 300) -> int:
    """Append live OHLCV rows to the archive. Idempotent: bars already present
    for (symbol, bar-ts, interval) are skipped. Returns rows inserted.

    Accepts either the broker wire frame (t/o/h/l/c/v + symbol) or the
    normalized frame (datetime/open/high/low/close + symbol).
    """
    import pandas as pd
    if df is None or getattr(df, 'empty', True):
        return 0
    raw = df.copy()
    if 'datetime' not in raw.columns and 't' in raw.columns:
        raw['datetime'] = pd.to_datetime(raw['t'], unit='s', utc=True)
    elif 'datetime' in raw.columns:
        raw['datetime'] = pd.to_datetime(raw['datetime'])
    raw['datetime'] = pd.to_datetime(raw['datetime'])
    if raw['datetime'].dt.tz is not None:
        raw['datetime'] = raw['datetime'].dt.tz_convert('UTC').dt.tz_localize(None)
    if 'symbol' not in raw.columns:
        return 0

    cands = []
    for _, r in raw.iterrows():
        ts = r['datetime']
        cands.append({
            'symbol': str(r['symbol']),
            'ts': ts.to_pydatetime(),
            'interval': interval,
            'open': _candle_field(r, 'o', 'open'),
            'high': _candle_field(r, 'h', 'high'),
            'low': _candle_field(r, 'l', 'low'),
            'close': _candle_field(r, 'c', 'close'),
            'volume': _candle_field(r, 'v', 'volume', 0.0) or 0.0,
        })
    if not cands:
        return 0

    symbols = {c['symbol'] for c in cands}
    ts_min = min(c['ts'] for c in cands)
    ts_max = max(c['ts'] for c in cands)
    q = select(models.Candle.symbol, models.Candle.ts, models.Candle.interval).where(
        models.Candle.symbol.in_(symbols),
        models.Candle.interval == interval,
        models.Candle.ts >= ts_min,
        models.Candle.ts <= ts_max)
    existing = {(r.symbol, r.ts, r.interval) for r in (await session.execute(q)).all()}
    fresh = [models.Candle(**c) for c in cands
             if (c['symbol'], c['ts'], c['interval']) not in existing]
    if fresh:
        session.add_all(fresh)
        await session.commit()
    return len(fresh)


async def load_candles(session: AsyncSession, symbols=None, start=None, end=None,
                       interval: int = 300):
    """Load archived candles as a normalized DataFrame (symbol, datetime UTC,
    open/high/low/close/volume) ordered by symbol+ts. Empty frame when none."""
    import pandas as pd
    q = select(models.Candle).where(models.Candle.interval == interval)
    if symbols:
        q = q.where(models.Candle.symbol.in_(symbols))
    if start is not None:
        q = q.where(models.Candle.ts >= start)
    if end is not None:
        q = q.where(models.Candle.ts < end)
    q = q.order_by(models.Candle.symbol, models.Candle.ts)
    rows = list((await session.execute(q)).scalars().all())
    if not rows:
        return pd.DataFrame(columns=['symbol', 'datetime', 'open', 'high',
                                     'low', 'close', 'volume'])
    return pd.DataFrame([{
        'symbol': r.symbol, 'datetime': r.ts.replace(tzinfo=timezone.utc),
        'open': r.open, 'high': r.high,
        'low': r.low, 'close': r.close, 'volume': r.volume,
    } for r in rows])


async def candle_stats(session: AsyncSession) -> dict:
    """Archive size + coverage (bars per symbol, earliest/latest ts)."""
    rows = (await session.execute(
        select(models.Candle.symbol, func.count(models.Candle.id),
               func.min(models.Candle.ts), func.max(models.Candle.ts))
        .group_by(models.Candle.symbol))).all()
    total = sum(r[1] for r in rows) if rows else 0
    return {
        'total_candles': total,
        'symbols': len(rows) if rows else 0,
        'by_symbol': {r[0]: {'count': r[1], 'first': str(r[2]), 'last': str(r[3])}
                      for r in rows},
    }
