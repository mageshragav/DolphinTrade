"""API routers: monitor, trades, decisions, agents, settings + websocket."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import ws
from app.config import get_settings
from app.db import get_db
from app.services import persistence, risk as risk_svc
from app.connectors.olymp import token_expiry, token_ok

LOGGER = logging.getLogger('dolphin')

router = APIRouter(prefix='/api')

# runtime handle set by main
from app.runtime_ctx import RUNTIME


def decision_to_dict(d) -> dict:
    return {
        'id': d.id, 'ts': d.ts.isoformat() if d.ts else None, 'symbol': d.symbol,
        'tf': d.tf, 'expiry': d.expiry, 'action': d.action,
        'p_call': d.p_call, 'p_put': d.p_put, 'best_prob': d.best_prob,
        'ev_score': d.ev_score, 'candle_close': d.candle_close,
        'candle_open': d.candle_open, 'candle_close_price': d.candle_close_price,
        'entry_price': d.entry_price, 'target_price': d.target_price,
        'stop_loss': d.stop_loss, 'atr': d.atr,
        'sentiment_bias': d.sentiment_bias, 'manipulation_risk': d.manipulation_risk,
        'news_veto': d.news_veto, 'news_next': d.news_next, 'headline': d.headline,
        'model': d.model, 'rationale': d.rationale,
    }


def trade_to_dict(t) -> dict:
    return {
        'id': t.id, 'ts': t.ts.isoformat() if t.ts else None, 'symbol': t.symbol,
        'tf': t.tf, 'expiry': t.expiry, 'action': t.action,
        'candle_open': t.candle_open, 'candle_close': t.candle_close,
        'entry': t.entry, 'take_profit': t.take_profit, 'stop_loss': t.stop_loss,
        'expiry_time': t.expiry_time.isoformat() if t.expiry_time else None,
        'status': t.status, 'exit_price': t.exit_price, 'result': t.result,
        'broker_ref': t.broker_ref, 'broker_status': t.broker_status,
        'winperc': t.winperc, 'order_type': t.order_type,
        'dry_run': t.dry_run, 'shadow': t.shadow, 'stake': t.stake,
        'reason': t.reason,
    }


# ---------------------------------------------------------------------------
# monitor
# ---------------------------------------------------------------------------

@router.get('/monitor/status')
async def monitor_status(session: AsyncSession = Depends(get_db)):
    limits = await risk_svc.get_limits(session)
    breaker = await risk_svc.circuit_breaker_status(session)
    killed = await risk_svc.kill_switch(session)
    trades = await persistence.trades_today(session)
    losses = await persistence.losses_today(session)
    sch = RUNTIME['scheduler']
    drift = await risk_svc.circuit_breaker_status(session)
    return {
        'running': bool(sch and sch.running),
        'kill_switch': killed,
        'dry_run': limits.get('dry_run', True),
        'trade_mode': limits.get('trade_mode', 'dry'),
        'trades_today': trades,
        'losses_today': round(losses, 2),
        'max_trades_per_day': limits.get('max_trades_per_day'),
        'max_daily_loss_pct': limits.get('max_daily_loss_pct'),
        'circuit_breaker': breaker,
        'order_type': (risk_svc.normalize_order_types(limits) or ['binary'])[0],
        'order_types': risk_svc.normalize_order_types(limits),
        'multiplicator': limits.get('multiplicator', 100),
        'theta': get_settings().theta,
        'combos': get_settings().combos,
        'hours_window': get_settings().hours_window,
        'pairs': get_settings().pairs,
        'equity': limits.get('equity', 1000.0),
        'stake_pct': limits.get('stake_pct', 0.01),
        'model_count': len(RUNTIME['runtime'].ml.combo_models) if RUNTIME['runtime'] else 0,
        'news_events': len(RUNTIME['runtime'].news.events) if RUNTIME['runtime'] else 0,
        'token_ok': token_ok(),
        'token_expires_at': str(token_expiry()) if token_expiry() else None,
        'drift': drift,
    }


class StartStop(BaseModel):
    action: str = Field(pattern='^(start|stop)$')


class TokenUpdate(BaseModel):
    access_token: str = Field(min_length=50)


@router.post('/token')
async def update_token_api(body: TokenUpdate):
    """Hot-swap the olymp session token without restarting the server."""
    rt = RUNTIME['runtime']
    if rt is None or getattr(rt, 'connector', None) is None:
        return {'ok': False, 'msg': 'connector not initialized'}
    try:
        ok = rt.connector.set_token(body.access_token)
    except Exception as e:
        return {'ok': False, 'msg': f'token swap failed: {e}'}
    exp = token_expiry()
    return {'ok': ok, 'token_expires_at': str(exp) if exp else None,
            'msg': 'token updated and verified' if ok else 'token update failed'}


@router.get('/instruments')
async def get_instruments_api():
    """Live instrument payouts + tradability from the broker websocket."""
    from app.connectors import instruments
    ok = instruments.refresh()
    snap = instruments.snapshot()
    return {'ok': ok, 'ts': snap['ts'],
            'profitability': snap['profitability'],
            'pairs': sorted(p for p, v in snap['profitability'].items()
                            if v and v >= 50)}


@router.get('/candles/stats')
async def candle_stats_api(session: AsyncSession = Depends(get_db)):
    """Historical OHLCV archive size + per-symbol coverage."""
    return await persistence.candle_stats(session)


class BacktestRequest(BaseModel):
    combos: str | None = None            # '5m:15m,15m:1h' (defaults to settings)
    theta: float | None = None
    start: str | None = None             # ISO date/time (UTC)
    end: str | None = None
    order_types: list[str] | None = None  # ['binary'] | ['multiplier'] | both
    stake_pct: float | None = None
    equity: float | None = None
    cooldown_min: int | None = None
    max_trades_per_day: int | None = None


@router.post('/backtest/run')
async def backtest_run(body: BacktestRequest, session: AsyncSession = Depends(get_db)):
    """Replay archived candles through the production decision pipeline and
    return a simulated trade log, equity curve and per-group stats."""
    import asyncio
    from app.trading.scheduler import parse_combos
    from app.connectors import instruments

    settings = get_settings()
    combos = parse_combos(body.combos or settings.combos)
    candles = await persistence.load_candles(
        session, start=body.start, end=body.end)
    if candles.empty:
        return {'ok': False, 'msg': 'no archived candles in the requested window '
                                    '(the live bot archives 5m bars on every cycle)'}
    rt = RUNTIME.get('runtime')
    ml = rt.ml if rt is not None else None
    if ml is None:
        from dolphin.ml_service import DecisionService
        ml = DecisionService(theta=body.theta if body.theta is not None else 0.65)

    from app.backtest.engine import run_backtest_sync
    kwargs = {
        'combos': combos,
        'order_types': body.order_types or ['binary'],
        'instruments_payout': instruments.payout_for,
    }
    for f in ('theta', 'stake_pct', 'equity', 'cooldown_min', 'max_trades_per_day'):
        v = getattr(body, f)
        if v is not None:
            kwargs[f] = v
    result = await asyncio.to_thread(run_backtest_sync, ml, candles, **kwargs)
    result['ok'] = True
    # auto-save the benchmark for the drift monitor when the sample is large
    # enough to be meaningful (>= 20 settled trades)
    summary = result.get('summary', {})
    if summary.get('settled', 0) >= 20:
        await risk_svc.set_benchmark(
            session, summary['win_rate'] or 0.6, 'backtest',
            trades=summary['settled'])
        result['benchmark_saved'] = True
    return result


@router.get('/accounts')
async def get_accounts_api():
    """Broker accounts (demo/real) with balances."""
    import json as _json
    import urllib.request
    from common import constants as const
    req = urllib.request.Request('https://gw.olymptrade.com/api/accounts/list/v2',
                                 data=_json.dumps({'with_archive': True}).encode(),
                                 headers={
                                     'accept': '*/*', 'content-type': 'application/json',
                                     'cookie': const.cookies_str,
                                     'origin': 'https://olymptrade.com',
                                     'referer': 'https://olymptrade.com/',
                                     'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) '
                                                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                                                   'Chrome/151.0.0.0 Safari/537.36',
                                     'x-cid-app': 'web@OlympTrade@2026.3.2330613@2330613',
                                     'x-cid-device': '@@desktop',
                                     'x-cid-os': 'linux@none', 'x-cid-ver': '1'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read().decode())
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    accounts = data.get('accounts') if isinstance(data, dict) else data
    if not isinstance(accounts, list):
        return {'ok': False, 'msg': 'unexpected response'}
    out = []
    for a in accounts:
        bal = a.get('balance') or {}
        out.append({
            'id': a.get('id'), 'name': a.get('name'), 'group': a.get('group'),
            'type': a.get('type'), 'status': a.get('status'),
            'currency': a.get('currency'),
            'balance': bal.get('amount', 0),
        })
    return {'ok': True, 'accounts': out}


@router.get('/pairs')
async def get_pairs_api():
    """Available broker instruments: ftt (fixed-time) and fx (multiplier)."""
    import json as _json
    import urllib.request
    from common import constants as const
    body = _json.dumps({"list": ["ftt_pairs", "ftt_pairs_default",
                                  "fx_pairs", "fx_pairs_default"]}).encode()
    req = urllib.request.Request('https://gw.olymptrade.com/api/user/values/v1',
                                 data=body, headers={
                                     'accept': '*/*', 'content-type': 'application/json',
                                     'cookie': const.cookies_str,
                                     'origin': 'https://olymptrade.com',
                                     'referer': 'https://olymptrade.com/',
                                     'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) '
                                                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                                                   'Chrome/151.0.0.0 Safari/537.36',
                                     'x-cid-app': 'web@OlympTrade@2026.3.2330613@2330613',
                                     'x-cid-device': '@@desktop',
                                     'x-cid-os': 'linux@none', 'x-cid-ver': '1'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = _json.loads(r.read().decode())
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    ftt = [p.get('id') for p in (data.get('ftt_pairs') or [])]
    fx = [p.get('id') for p in (data.get('fx_pairs') or [])]
    return {
        'ok': True,
        'ftt_default': (data.get('ftt_pairs_default') or {}).get('id'),
        'fx_default': (data.get('fx_pairs_default') or {}).get('id'),
        'ftt_currency': sorted(i for i in ftt if len(i) == 6 and i.isupper()
                               and i not in ('BRZU', 'UVXY', 'AMZN', 'AAPL',
                                             'BMW', 'KO', 'FCE', 'BA', 'DIS',
                                             'YM', 'FDAX', 'QID', 'IYR', 'CAT',
                                             'CVX', 'CSCO', 'DAX', 'EURUSD_OTC')
                               and not i.endswith('_OTC')),
        'ftt_count': len(ftt), 'fx_count': len(fx),
    }


@router.post('/monitor/control')
async def monitor_control(body: StartStop):
    sch = RUNTIME['scheduler']
    if sch is None:
        return {'ok': False, 'msg': 'scheduler not initialized'}
    if body.action == 'start':
        sch.running = True
        return {'ok': True, 'running': True}
    sch.running = False
    return {'ok': True, 'running': False}


@router.post('/monitor/kill')
async def kill_switch(body: dict, session: AsyncSession = Depends(get_db)):
    on = bool(body.get('on', True))
    await risk_svc.set_kill_switch(session, on)
    return {'ok': True, 'kill_switch': on}


# ---------------------------------------------------------------------------
# trades / decisions / signals
# ---------------------------------------------------------------------------

@router.get('/trades')
async def list_trades(n: int = 30, session: AsyncSession = Depends(get_db)):
    rows = await persistence.last_trades(session, n)
    return [trade_to_dict(t) for t in rows]


@router.post('/demo/seed')
async def demo_seed(session: AsyncSession = Depends(get_db)):
    """Insert sample trades so the results view is populated immediately
    (clearly labeled as demo/dry-run). Real trades replace these over time."""
    from datetime import timedelta
    from app.services import persistence as p
    base = datetime.now(timezone.utc)
    samples = [
        ('FX:EURUSD', 'CALL', '15m', 1.08840, 1.08920, 1.08800, 'WIN', 10.0),
        ('FX:EURJPY', 'PUT', '30m', 171.240, 171.200, 171.260, 'WIN', 10.0),
        ('FX:GBPUSD', 'CALL', '15m', 1.35060, 1.35120, 1.35020, 'LOSS', 10.0),
        ('FX:USDJPY', 'PUT', '1h', 159.430, 159.300, 159.470, 'LOSS', 10.0),
        ('FX:EURGBP', 'CALL', '30m', 0.84495, 0.84560, 0.84460, 'WIN', 10.0),
        ('FX:USDCAD', 'PUT', '15m', 1.39320, 1.39270, 1.39350, 'WIN', 10.0),
        ('FX:EURAUD', 'CALL', '1h', 1.63470, 1.63600, 1.63420, 'OPEN', 10.0),
    ]
    for i, (sym, action, expiry, entry, tp, sl, result, stake) in enumerate(samples):
        exp = base + timedelta(minutes=15)
        if expiry.endswith('h'):
            exp = base + timedelta(hours=int(expiry[:-1]))
        elif expiry != '15m':
            exp = base + timedelta(minutes=int(expiry.rstrip('m')))
        status = 'expired' if result != 'OPEN' else 'open'
        await p.record_trade(session, {
            'symbol': sym, 'tf': '5m', 'expiry': expiry, 'action': action,
            'candle_open': entry, 'candle_close': entry,
            'entry': entry, 'take_profit': tp, 'stop_loss': sl,
            'expiry_time': exp, 'status': status,
            'exit_price': entry - 0.0003 if result == 'LOSS' else entry + 0.0003
            if result == 'WIN' else None,
            'result': result if result != 'OPEN' else None,
            'dry_run': True, 'stake': stake, 'reason': 'demo seed',
        })
    return {'ok': True, 'seeded': len(samples)}


@router.get('/analytics')
async def analytics_api(session: AsyncSession = Depends(get_db)):
    """Full performance analytics: equity curve, streaks, heatmaps, drift."""
    from app.services import analytics as analytics_svc
    return await analytics_svc.analytics(session)


@router.get('/analytics/report')
async def analytics_report_api(session: AsyncSession = Depends(get_db)):
    """Generate the nightly report text without sending it (preview)."""
    from app.services import analytics as analytics_svc
    a = await analytics_svc.analytics(session)
    return {'report': analytics_svc.build_nightly_report(a)}


@router.get('/analytics/shadow')
async def analytics_shadow(session: AsyncSession = Depends(get_db)):
    """Shadow (paper) ledger vs live vs dry-run - win rate + net PnL side by side."""
    trades = await persistence.last_trades(session, n=500)

    def summarize(rows):
        settled = [t for t in rows if t.result in ('WIN', 'LOSS')]
        if not settled:
            return {'trades': len(rows), 'settled': 0, 'win_rate': None,
                    'net_pnl': 0.0, 'profit_factor': None}
        wins = sum(1 for t in settled if t.result == 'WIN')
        gross_win = sum(t.stake * (t.winperc or 0) / 100 for t in settled if t.result == 'WIN')
        gross_loss = sum(t.stake for t in settled if t.result == 'LOSS')
        pnl = gross_win - gross_loss
        return {'trades': len(rows), 'settled': len(settled),
                'win_rate': round(wins / len(settled), 4),
                'net_pnl': round(pnl, 2),
                'profit_factor': round(gross_win / gross_loss, 3) if gross_loss else None}

    shadow = [t for t in trades if t.shadow]
    live = [t for t in trades if not t.shadow and not t.dry_run]
    dry = [t for t in trades if t.dry_run and not t.shadow]
    return {
        'shadow': summarize(shadow),
        'live': summarize(live),
        'dry': summarize(dry),
        'shadow_count': len(shadow), 'live_count': len(live), 'dry_count': len(dry),
    }


@router.get('/results')
async def results(n: int = 200, session: AsyncSession = Depends(get_db)):
    """Aggregated results tracking: summary stats + recent trades."""
    trades = await persistence.last_trades(session, n)
    settled = [t for t in trades if t.result in ('WIN', 'LOSS', 'DRAW')]
    wins = sum(1 for t in settled if t.result == 'WIN')
    losses = sum(1 for t in settled if t.result == 'LOSS')
    draws = sum(1 for t in settled if t.result == 'DRAW')
    open_count = sum(1 for t in trades if t.status == 'open')
    win_rate = wins / len(settled) if settled else None
    est_pnl = sum(t.stake * 0.88 for t in settled if t.result == 'WIN') - \
        sum(t.stake for t in settled if t.result == 'LOSS')
    by_symbol = {}
    for t in settled:
        s = by_symbol.setdefault(t.symbol, {'trades': 0, 'wins': 0, 'losses': 0})
        s['trades'] += 1
        s['wins'] += t.result == 'WIN'
        s['losses'] += t.result == 'LOSS'
    for s in by_symbol.values():
        s['win_rate'] = round(s['wins'] / s['trades'], 3) if s['trades'] else None
    return {
        'summary': {
            'total': len(trades),
            'settled': len(settled),
            'open': open_count,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'win_rate': round(win_rate, 4) if win_rate is not None else None,
            'est_pnl': round(est_pnl, 2),
            'dry_run': all(t.dry_run for t in trades) if trades else True,
        },
        'by_symbol': by_symbol,
        'trades': [trade_to_dict(t) for t in trades[:n]],
    }


@router.get('/decisions')
async def list_decisions(n: int = 100, session: AsyncSession = Depends(get_db)):
    rows = await persistence.last_decisions(session, n)
    return [decision_to_dict(d) for d in rows]


@router.get('/signals')
async def list_signals(n: int = 30, session: AsyncSession = Depends(get_db)):
    rows = await persistence.recent_signals(session, n)
    return [{'id': s.id, 'ts': s.ts.isoformat() if s.ts else None, 'symbol': s.symbol,
             'expiry': s.expiry, 'action': s.action, 'payload': s.payload,
             'telegram_status': s.telegram_status} for s in rows]


# ---------------------------------------------------------------------------
# agents
# ---------------------------------------------------------------------------

@router.get('/agents')
async def agents_status():
    rt = RUNTIME['runtime']
    if rt is None:
        return {'news_events': 0, 'sentiment': {}, 'next_event': None, 'llm': False}
    pairs = [p.strip() for p in get_settings().pairs.split(',') if p.strip()]
    sentiment = {p: rt.headlines.bias(f'FX:{p}') for p in pairs}
    nxt = rt.news.upcoming()
    nxt = nxt[0] if nxt else None
    return {
        'news_events': len(rt.news.events),
        'sentiment': sentiment,
        'next_event': nxt['title'] if nxt else None,
        'next_event_time': str(nxt['time']) if nxt else None,
        'llm': rt.headlines.llm is not None,
    }


@router.get('/agent-events')
async def agent_events(n: int = 50, session: AsyncSession = Depends(get_db)):
    rows = await persistence.recent_agent_events(session, n)
    return [{'ts': e.ts.isoformat() if e.ts else None, 'kind': e.kind,
             'symbol': e.symbol, 'summary': e.summary, 'payload': e.payload} for e in rows]


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

class SettingsUpdate(BaseModel):
    dry_run: bool | None = None
    trade_mode: str | None = None       # live | dry | shadow
    max_trades_per_day: int | None = None
    max_daily_loss_pct: float | None = None
    symbol_cooldown_min: int | None = None
    stake_pct: float | None = None
    equity: float | None = None
    order_type: str | None = None          # legacy single mode
    order_types: list[str] | None = None  # ['binary','multiplier'] both markets
    multiplicator: int | None = None
    sl_tp_mode: str | None = None          # signal_levels | atr (multiplier)
    atr_sl_mult: float | None = None
    atr_tp_mult: float | None = None
    hourly_floor: float | None = None      # hourly-guarantee primary tier
    hourly_floor_min: float | None = None  # fallback tier
    hw_stop_pct: float | None = None       # equity high-watermark stop
    daily_profit_target_pct: float | None = None   # tiered basket profit target
    loss_streak_reduce_after: int | None = None
    loss_streak_stake_factor: float | None = None
    news_blackout_min: int | None = None
    theta: float | None = None
    combos: str | None = None
    hours_window: str | None = None
    pairs: str | None = None
    hourly_guarantee: bool | None = None
    hourly_minute: int | None = None


@router.get('/settings')
async def get_settings_api(session: AsyncSession = Depends(get_db)):
    limits = await risk_svc.get_limits(session)
    s = get_settings()
    return {
        'dry_run': limits.get('dry_run'), 'trade_mode': limits.get('trade_mode', 'dry'),
        'max_trades_per_day': limits.get('max_trades_per_day'),
        'max_daily_loss_pct': limits.get('max_daily_loss_pct'),
        'symbol_cooldown_min': limits.get('symbol_cooldown_min'),
        'stake_pct': limits.get('stake_pct'), 'equity': limits.get('equity'),
        'order_type': (risk_svc.normalize_order_types(limits) or ['binary'])[0],
        'order_types': risk_svc.normalize_order_types(limits),
        'multiplicator': limits.get('multiplicator', 100),
        'sl_tp_mode': limits.get('sl_tp_mode', 'signal_levels'),
        'atr_sl_mult': limits.get('atr_sl_mult', 1.5),
        'atr_tp_mult': limits.get('atr_tp_mult', 3.0),
        'hw_stop_pct': limits.get('hw_stop_pct', 15.0),
        'daily_profit_target_pct': limits.get('daily_profit_target_pct', 10.0),
        'loss_streak_reduce_after': limits.get('loss_streak_reduce_after', 3),
        'loss_streak_stake_factor': limits.get('loss_streak_stake_factor', 0.5),
        'news_blackout_min': limits.get('news_blackout_min', 0),
        'hourly_floor': limits.get('hourly_floor', 0.58),
        'hourly_floor_min': limits.get('hourly_floor_min', 0.55),
        'theta': s.theta, 'combos': s.combos, 'hours_window': s.hours_window, 'pairs': s.pairs,
        'hourly_guarantee': s.hourly_guarantee, 'hourly_minute': s.hourly_minute,
    }


@router.put('/settings')
async def update_settings_api(body: SettingsUpdate, session: AsyncSession = Depends(get_db)):
    limits = await risk_svc.get_limits(session)
    for f in ['dry_run', 'trade_mode', 'max_trades_per_day', 'max_daily_loss_pct', 'symbol_cooldown_min',
              'stake_pct', 'equity', 'multiplicator', 'sl_tp_mode',
              'atr_sl_mult', 'atr_tp_mult', 'hw_stop_pct', 'hourly_floor',
              'hourly_floor_min',
              'daily_profit_target_pct', 'loss_streak_reduce_after',
              'loss_streak_stake_factor', 'news_blackout_min']:
        v = getattr(body, f)
        if v is not None:
            limits[f] = v
    if body.order_types is not None:
        limits['order_types'] = body.order_types
    elif body.order_type is not None:
        limits['order_types'] = [body.order_type]
    await risk_svc.set_limits(session, limits)

    s = get_settings()
    changed = False
    if body.theta is not None and body.theta != s.theta:
        s.theta = body.theta
        changed = True
    if body.combos and body.combos != s.combos:
        s.combos = body.combos
        changed = True
    if body.hours_window is not None and body.hours_window != s.hours_window:
        s.hours_window = body.hours_window
    if body.hourly_guarantee is not None and body.hourly_guarantee != s.hourly_guarantee:
        s.hourly_guarantee = body.hourly_guarantee
        changed = True
    if body.hourly_minute is not None and body.hourly_minute != s.hourly_minute:
        s.hourly_minute = body.hourly_minute
    if body.pairs and body.pairs != s.pairs:
        s.pairs = body.pairs
    if changed:
        rt = RUNTIME['runtime']
        if rt:
            if hasattr(rt.ml, 'theta'):
                rt.ml.theta = s.theta
    return {'ok': True}


# ---------------------------------------------------------------------------
# websocket
# ---------------------------------------------------------------------------

@router.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await ws.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws.disconnect(websocket)
    except Exception:
        ws.disconnect(websocket)
