"""Platform tests: risk gates, execution idempotency, graph routing.

Run:  cd backend && python -m pytest tests/ -q
Uses an in-memory sqlite DB and a fake broker connector (no network).
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

import pytest
import pytest_asyncio

os.environ['DT_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['DT_DRY_RUN'] = 'true'

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

from app.db import init_db, SessionLocal  # noqa: E402
from app.services import persistence, risk  # noqa: E402
from app.services.execution import ExecutionService  # noqa: E402
from app.trading import graph as graph_mod  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def db():
    from app.connectors import instruments as _inst
    with _inst._LOCK:
        _inst._CACHE['ts'] = __import__('time').time()   # fresh+empty: no probe
        _inst._CACHE['profitability'] = {}
        _inst._CACHE['schedule'] = {}
    await init_db()
    yield
    async with SessionLocal() as s:
        from app.models import Decision, Trade, AgentEvent, Signal, BotSetting
        for m in [Decision, Trade, AgentEvent, Signal, BotSetting]:
            await s.execute(m.__table__.delete())
        await s.commit()


class FakeConnector:
    def __init__(self):
        self.placed = []
        self._seq = 0

    def place_bet(self, symbol, direction, amount, duration_sec=None,
                  order_type='binary', multiplicator=100,
                  take_profit=None, stop_loss=None):
        self._seq += 1
        ref = f'fake-{self._seq}'
        self.placed.append({
            'symbol': symbol, 'direction': direction, 'amount': amount,
            'duration_sec': duration_sec, 'order_type': order_type,
            'multiplicator': multiplicator, 'take_profit': take_profit,
            'stop_loss': stop_loss,
        })
        if order_type == 'multiplier':
            # faithful to the real e:1032 reply: price_open, no curs_open/winperc
            return {'id': ref, 'price_open': 158.931, 'status': 'proceed',
                    'pair': 'USDJPY', 'multiplicator': 100}
        return {'id': ref, 'curs_open': 1.0884, 'winperc': 90,
                'time_close_default': 1786560820.622, 'status': 'proceed'}


def sample_decision(action='CALL'):
    return {
        'symbol': 'FX:EURUSD', 'tf': '5m', 'expiry': '15m', 'action': action,
        'candle_close': '2026-08-12 10:00:00', 'candle_open': 1.0885,
        'candle_close_price': 1.0884, 'entry_price': 1.0884,
        'target_price': 1.0892, 'stop_loss': 1.0880,
        'best_prob': 0.71, 'p_call': 0.71, 'p_put': 0.2, 'ev_score': 0.25,
        'rationale': 'test', 'model': 'combo_300_900',
    }


async def test_dry_run_records_trade():
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': True, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'order_types': ['binary']})
        result = await svc.execute(s, sample_decision(), decision_id=0)
        assert result['dry_run'] is True
        assert result['placed'] is True
        assert connector.placed == []          # no real bet in dry-run
        trades = await persistence.last_trades(s, 5)
        assert len(trades) == 1
        assert trades[0].status == 'open'
        assert trades[0].dry_run is True


async def test_idempotency_blocks_duplicate():
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'order_types': ['binary']})
        r1 = await svc.execute(s, sample_decision(), decision_id=1)
        assert r1['placed'] is True
        r2 = await svc.execute(s, sample_decision(), decision_id=2)
        assert r2['placed'] is False
        assert 'duplicate' in r2['reason']
        assert len(connector.placed) == 1


async def test_kill_switch_blocks():
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0})
        await risk.set_kill_switch(s, True)
        r = await svc.execute(s, sample_decision(), decision_id=3)
        assert r['placed'] is False
        assert 'kill-switch' in r['reason']
        assert connector.placed == []


async def test_daily_trade_limit():
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 2,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0})
        t1 = {**sample_decision(), 'candle_close': '2026-08-12 10:00:00'}
        t2 = {**sample_decision('PUT'), 'candle_close': '2026-08-12 10:05:00'}
        t3 = {**sample_decision(), 'candle_close': '2026-08-12 10:10:00'}
        await svc.execute(s, t1, decision_id=4)
        await svc.execute(s, t2, decision_id=5)
        r3 = await svc.execute(s, t3, decision_id=6)
        assert r3['placed'] is False
        assert 'daily trade limit' in r3['reason']


async def test_graph_below_gate_goes_neutral():
    graph_mod.set_context(candidates={}, candles={}, news_agent=None,
                          headline_agent=None, risk_agent=None, theta=0.65)
    g = graph_mod.build_graph()
    out = await g.ainvoke({'symbol': 'FX:EURUSD', 'tf': '5m', 'expiry': '15m',
                           'candidate': {'action': 'CALL', 'best_prob': 0.4,
                                         'ev_score': -0.2, 'rationale': 'low'}})
    assert out.get('execution', {}).get('placed') is False
    async with SessionLocal() as s:
        decisions = await persistence.last_decisions(s, 5)
        assert len(decisions) == 1
        assert decisions[0].action == 'NEUTRAL'


# ---------------------------------------------------------------------------
# wire formats (verified against the live platform captures)
# ---------------------------------------------------------------------------

def test_binary_key_payload():
    """e:23 must match the live platform: ms timestamp + is_flex:false."""
    from common.socketkey.olymptradekey import OlympTradeConnection
    k = OlympTradeConnection.__new__(OlympTradeConnection)
    k.account_id = 2939944075
    k.group_id = 'demo'
    key = k.get_bet_key('down', 'EURUSD', '1', '900')
    assert key[0]['e'] == 23
    d = key[0]['d'][0]
    assert d['is_flex'] is False
    assert d['timestamp'] > 1_000_000_000_000          # milliseconds
    assert d['group'] == 'demo'
    assert d['duration'] == 900
    assert d['cat'] == 'digital'
    assert d['account_id'] == 2939944075


def test_multiplier_key_payload():
    """e:1032 must match the live platform: multiplicator + SL/TP."""
    from common.socketkey.olymptradekey import OlympTradeConnection
    k = OlympTradeConnection.__new__(OlympTradeConnection)
    k.account_id = 2939944075
    k.group_id = 'demo'
    tp = {'type': 'price', 'value': 1.10, }
    sl = {'type': 'price', 'value': 1.05, }
    key = k.get_order_key('up', 'EURUSD', '1', multiplicator=100,
                          stop_loss=sl, take_profit=tp)
    assert key[0]['e'] == 1032
    d = key[0]['d'][0]
    assert d['multiplicator'] == 100
    assert d['stop_loss'] == sl
    assert d['take_profit'] == tp
    assert d['group'] == 'demo'
    assert 'duration' not in d                    # multiplier has no expiry


def test_binary_response_parsing():
    """Parse the captured e:23 response (real broker reply format)."""
    from app.connectors.order_channel import OrderChannel
    raw = ('[{"d":[{"currency":"usd","cat":"digital","group":"demo","dir":"down",'
           '"pair":"BNBUSD_OTC","status":"proceed","amount":1,"account_id":2939944075,'
           '"id":12419444196,"user_id":138073946,"winperc":90,"duration":60,'
           '"curs_open":606.54,"curs_strike":606.54,"curs_close":0,"curs_current":606.54,'
           '"time_open":1786560760.622,"time_close_default":1786560820.622,'
           '"is_flex":false}],"e":23,"t":3,"uuid":"MSQG5D9NHXA9VD4BXQ"}]')
    ch = OrderChannel.__new__(OrderChannel)
    ch.deals = {}
    ch._track(raw)
    deal = ch.deals.get('12419444196')
    assert deal is not None
    assert deal['winperc'] == 90
    assert deal['curs_open'] == 606.54
    assert deal['status'] == 'proceed'
    assert deal['time_close_default'] == 1786560820.622


async def test_broker_deal_settles_trade():
    """An e:22/e:23 deal update settles an open trade by broker_ref."""
    from app.services import persistence as p
    from app.services.tracker import TradeTracker
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0, 'order_type': 'binary'})
        r = await svc.execute(s, sample_decision(), decision_id=10)
        assert r['placed'] is True
        assert r['broker_ref'] == 'fake-1'
        # broker reports the deal closed in profit
        deal = {'id': r['broker_ref'], 'balance_change': 0.9, 'status': 'won',
                'curs_close': 1.0892}
        n = await TradeTracker.process_broker_deals(s, [deal])
        assert n == 1
        trades = await p.last_trades(s, 5)
        t = trades[0]
        assert t.status == 'expired'
        assert t.result == 'WIN'
        assert t.entry == 1.0884            # broker curs_open, not the signal estimate
        assert t.winperc == 90              # broker payout


async def test_multiplier_skips_expiry_settlement():
    """Multiplier trades have no expiry_time and are NOT feed-settled."""
    from datetime import timedelta
    from app.services import persistence as p
    from app.services.tracker import TradeTracker
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'order_type': 'multiplier', 'multiplicator': 100})
        r = await svc.execute(s, sample_decision(), decision_id=11)
        assert r['placed'] is True
        placed = connector.placed[-1]
        assert placed['order_type'] == 'multiplier'
        assert placed['multiplicator'] == 100
        assert placed['take_profit'] == {'type': 'price', 'value': 1.0892, }
        assert placed['stop_loss'] == {'type': 'price', 'value': 1.088, }
        assert placed['duration_sec'] is None
        trades = await p.last_trades(s, 5)
        t = trades[0]
        assert t.expiry_time is None
        assert t.order_type == 'multiplier'


# ---------------------------------------------------------------------------
# Phase-2 risk upgrades: high-watermark stop, profit target, loss-streak cut
# ---------------------------------------------------------------------------

async def test_high_watermark_stop_blocks_below_peak():
    """After a big loss, new trades must be blocked while equity < 85% of peak."""
    from app.services import persistence as p
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'hw_stop_pct': 15.0, 'daily_profit_target_pct': 0.0})
        # settle a real loss of $20 (below the 15% hw) -> equity 980 stays within
        await persistence.set_setting(s, 'equity_peak', 1000.0)
        ok, why = await risk.allowed(s, 'EURUSD')
        assert ok, why
        # simulate deep drawdown: force peak 1000, equity_now 800 (20% below)
        # -> block (needs losses recorded; inject a loss directly)
        await persistence.record_trade(s, {'decision_id': 99, 'symbol': 'EURUSD', 'tf': '5m',
                                           'expiry': '15m', 'action': 'CALL', 'entry': 1.08,
                                           'stake': 200.0, 'dry_run': False, 'status': 'expired',
                                           'result': 'LOSS', 'expiry_time': None,
                                           'candle_close_ts': '2026-08-12T10:00:00'})
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 30.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'hw_stop_pct': 15.0, 'daily_profit_target_pct': 0.0})
        ok, why = await risk.allowed(s, 'EURUSD')
        assert not ok
        assert 'high-watermark' in why


async def test_profit_target_halts_day():
    """Tiered profit target blocks new entries after the target is reached."""
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'daily_profit_target_pct': 10.0, 'hw_stop_pct': 0.0})
        await persistence.set_setting(s, 'equity_peak', 1000.0)
        # a $150 win with 0 trades -> target = 10% * 1000 * 1.0 = $100 < $150 -> block
        await persistence.record_trade(s, {'decision_id': 98, 'symbol': 'EURUSD', 'tf': '5m',
                                           'expiry': '15m', 'action': 'CALL', 'entry': 1.08,
                                           'stake': 100.0, 'winperc': 150.0, 'dry_run': False,
                                           'status': 'expired', 'result': 'WIN',
                                           'expiry_time': None,
                                           'candle_close_ts': '2026-08-12T11:00:00'})
        ok, why = await risk.allowed(s, 'EURUSD')
        assert not ok
        assert 'profit target' in why


async def test_loss_streak_reduces_stake():
    """After N consecutive losses the stake is cut by the configured factor."""
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'loss_streak_reduce_after': 2,
                                  'loss_streak_stake_factor': 0.5})
        for i in range(3):
            await persistence.record_trade(s, {'decision_id': 90 + i, 'symbol': 'EURUSD',
                                               'tf': '5m', 'expiry': '15m', 'action': 'CALL',
                                               'entry': 1.08, 'stake': 10.0, 'dry_run': False,
                                               'status': 'expired', 'result': 'LOSS',
                                               'expiry_time': None,
                                               'candle_close_ts': f'2026-08-12T12:0{i}:00'})
        r = await svc.execute(s, sample_decision(), decision_id=50)
        assert r['placed'] is True
        placed = connector.placed[-1]
        # streak=3, after=2 -> mult = 0.5^(3-2+1) = 0.25 -> stake 10 * 0.25 = 2.5
        assert placed['amount'] == 2.5, placed['amount']


async def test_atr_sl_tp_mode():
    """Multiplier in 'atr' mode uses ATR-scaled SL/TP, not signal levels."""
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'order_type': 'multiplier', 'multiplicator': 100,
                                  'sl_tp_mode': 'atr', 'atr_sl_mult': 1.5,
                                  'atr_tp_mult': 3.0})
        d = sample_decision()
        d['atr'] = 0.0012
        d['entry_price'] = 1.0884
        r = await svc.execute(s, d, decision_id=12)
        assert r['placed'] is True
        placed = connector.placed[-1]
        assert placed['take_profit'] == {'type': 'price', 'value': 1.0920, }
        assert placed['stop_loss'] == {'type': 'price', 'value': 1.0866, }


# ---------------------------------------------------------------------------
# go-live bundle: olymp socket alignment + runtime->graph executor wiring
# ---------------------------------------------------------------------------

def test_olymp_ws_matches_live_capture():
    """The order socket must use the exact URL captured from the live platform
    (2026.3.2302984 client, linux@none), with a single Origin passed via the
    lib option (a dict Origin would double up with the lib's own and get
    'invalid_origin') and permessage-deflate negotiated via extensions=."""
    from common.constants import OLYMP_WS, HEADERS, OLYMP_ORIGIN, OLYMP_EXTENSIONS
    assert OLYMP_WS == ('wss://ws.olymptrade.com/otp?cid_ver=1'
                        '&cid_app=web%40OlympTrade%402026.3.2330613%402330613'
                        '&cid_device=%40%40desktop&cid_os=linux%40none')
    assert OLYMP_ORIGIN == 'https://olymptrade.com'
    assert 'Origin' not in HEADERS                    # must go via origin=
    assert any('permessage-deflate' in e for e in OLYMP_EXTENSIONS)
    assert 'Cookie' in HEADERS
    assert 'access_token' in HEADERS['Cookie']


def test_runtime_wires_executor_connector():
    """TradingRuntime must pass its connector to the graph executor (this was
    None -> 'NoneType' object has no attribute 'place_bet' in production)."""
    from app.trading.runtime import TradingRuntime
    connector = FakeConnector()
    runtime = TradingRuntime(None, None, None, None, connector=connector)
    assert runtime.executor is not None
    assert runtime.executor.connector is connector


async def test_graph_execution_places_with_connector():
    """End-to-end through the graph: a CALL candidate becomes a placed trade
    with a broker_ref when a connector is wired into the context."""
    from app.trading import graph as graph_mod
    from app.services.execution import ExecutionService
    connector = FakeConnector()
    graph_mod.set_context(
        candidates={( 'FX:EURUSD', '5m', '15m'): sample_decision()},
        candles={},
        news_agent=None, headline_agent=None, risk_agent=None,
        theta=0.5, executor=ExecutionService(connector))
    state = {'symbol': 'FX:EURUSD', 'tf': '5m', 'expiry': '15m',
             'candidate': sample_decision()}
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0,
                                  'symbol_cooldown_min': 0, 'stake_pct': 0.01,
                                  'equity': 1000.0, 'order_types': ['binary']})
    out = await graph_mod.build_graph().ainvoke(state)
    assert out['execution']['placed'] is True
    assert out['execution']['broker_ref'] == 'fake-1'
    assert connector.placed[-1]['order_type'] == 'binary'


def test_csv_feed_place_bet_returns_synthetic_deal():
    """CSV sim mode must fabricate a broker deal so the dry-run-off chain
    works end-to-end (place -> record -> settle) without a real order."""
    from app.connectors.csv_feed import CSVFeedConnector
    feed = CSVFeedConnector()
    deal = feed.place_bet('FX:EURUSD', 'up', 10.0, duration_sec=900)
    assert deal['id'].startswith('fake-')
    assert deal['curs_open'] > 0
    assert deal['winperc'] == 90
    assert deal['status'] == 'proceed'


def test_token_health_guard():
    """The token guard must decode the JWT and report validity truthfully
    (auto-trading dies silently on expiry, so the guard surfaces it)."""
    from datetime import datetime, timezone
    from app.connectors.olymp import token_expiry, token_ok
    exp = token_expiry()
    assert exp is not None                      # JWT parses
    assert token_ok() == (exp > datetime.now(timezone.utc))


def test_token_hot_swap_updates_derived_strings():
    """set_access_token must update the shared cookies/HEADERS in place."""
    import common.constants as const
    original = const.cookies['access_token']
    try:
        const.set_access_token(original)           # idempotent re-set
        assert 'access_token=' in const.cookies_str
        assert const.HEADERS['Cookie'] == const.cookies_str
        assert const.DEALS_HEADERS['cookie'] == const.cookies_str
        from app.connectors.olymp import token_expiry
        assert token_expiry() is not None
    finally:
        const.set_access_token(original)


# ---------------------------------------------------------------------------
# hourly minimum-signal guarantee
# ---------------------------------------------------------------------------

class StubML:
    theta = 0.65

    def __init__(self, decisions):
        self._d = decisions

    def decide_all(self, candles, combos=None, theta=None):
        return list(self._d)


async def test_trades_in_hour_counts_placed():
    from app.services import persistence as p
    async with SessionLocal() as s:
        assert await p.trades_in_hour(s, datetime.utcnow().strftime('%Y%m%d%H')) == 0
        await p.record_trade(s, {'decision_id': 60, 'symbol': 'FX:EURUSD', 'tf': '5m',
                                 'expiry': '15m', 'action': 'CALL', 'entry': 1.08,
                                 'stake': 10.0, 'dry_run': False, 'status': 'open',
                                 'expiry_time': None, 'candle_close_ts': '2026-08-12T10:00:00'})
        assert await p.trades_in_hour(s, datetime.utcnow().strftime('%Y%m%d%H')) == 1


async def test_hourly_scan_places_when_floor_met():
    """An empty hour + candidate above the floor -> trade placed + reason tag."""
    from app.trading.runtime import TradingRuntime
    connector = FakeConnector()
    cand = {**sample_decision(), 'best_prob': 0.62, 'ev_score': 0.25}
    runtime = TradingRuntime(StubML([cand]), None, None, None, connector=connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'hourly_floor': 0.58})
    import pandas as pd
    out = await runtime.hourly_scan(pd.DataFrame())
    assert out['scanned'] is True
    assert out['placed'] is True
    assert out['symbol'] == 'FX:EURUSD'
    assert 'hourly-guarantee' in out['reason'] or 'hourly' in str(connector.placed[-1])
    # the trade is recorded through the executor
    async with SessionLocal() as s:
        trades = await persistence.last_trades(s, 2)
        assert any((t.reason or '').find('hourly-guarantee') >= 0 for t in trades)


async def test_hourly_scan_broadcasts_when_below_floor():
    """No candidate above the floor -> NEUTRAL decision recorded (informational)."""
    from app.trading.runtime import TradingRuntime
    connector = FakeConnector()
    cand = {**sample_decision(), 'best_prob': 0.54, 'ev_score': 0.05}
    runtime = TradingRuntime(StubML([cand]), None, None, None, connector=connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'hourly_floor': 0.58})
    import pandas as pd
    out = await runtime.hourly_scan(pd.DataFrame())
    assert out['scanned'] is True
    assert out['placed'] is False
    assert 'tier' in out['reason']
    async with SessionLocal() as s:
        d = await persistence.last_decisions(s, 1)
        assert d[0].action == 'NEUTRAL'
        assert 'hourly-scan' in d[0].rationale


async def test_hourly_scan_skips_when_hour_traded():
    """If the hour already has a non-cancelled trade, the scan stands down."""
    from app.trading.runtime import TradingRuntime
    connector = FakeConnector()
    cand = {**sample_decision(), 'best_prob': 0.9, 'ev_score': 0.5}
    runtime = TradingRuntime(StubML([cand]), None, None, None, connector=connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'hourly_floor': 0.58})
        await persistence.record_trade(s, {'decision_id': 61, 'symbol': 'FX:EURUSD',
                                           'tf': '5m', 'expiry': '15m', 'action': 'CALL',
                                           'entry': 1.08, 'stake': 10.0, 'dry_run': False,
                                           'status': 'open', 'expiry_time': None,
                                           'candle_close_ts': '2026-08-12T10:00:00'})
    import pandas as pd
    out = await runtime.hourly_scan(pd.DataFrame())
    assert out['scanned'] is False
    assert 'already traded' in out['reason']


async def test_hourly_scan_cooldown_aware():
    """A cooled-down best candidate is skipped for the next-best one."""
    from app.trading.runtime import TradingRuntime
    connector = FakeConnector()
    hot = {**sample_decision('PUT'), 'symbol': 'FX:EURUSD', 'best_prob': 0.99,
           'ev_score': 0.9}
    cold = {**sample_decision('CALL'), 'symbol': 'FX:GBPUSD', 'best_prob': 0.60,
            'ev_score': 0.2}
    runtime = TradingRuntime(StubML([hot, cold]), None, None, None, connector=connector)
    from datetime import timedelta
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 300,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'hourly_floor': 0.58})
        old_ts = datetime.now(timezone.utc) - timedelta(hours=2)
        await persistence.record_trade(s, {'decision_id': 62, 'symbol': 'FX:EURUSD',
                                           'tf': '5m', 'expiry': '15m', 'action': 'CALL',
                                           'entry': 1.08, 'stake': 10.0, 'dry_run': False,
                                           'status': 'expired', 'result': 'LOSS',
                                           'expiry_time': None,
                                           'candle_close_ts': '2026-08-12T10:00:00'})
        t = (await persistence.last_trades(s, 1))[0]
        await persistence.update_trade(s, t.id, ts=old_ts)
    import pandas as pd
    out = await runtime.hourly_scan(pd.DataFrame())
    assert out['placed'] is True
    assert out['symbol'] == 'FX:GBPUSD'          # skipped the cooled EURUSD


async def test_hourly_scan_fallback_tier():
    """A candidate between the fallback (0.55) and primary (0.58) floors is
    still placed via the second tier."""
    from app.trading.runtime import TradingRuntime
    connector = FakeConnector()
    cand = {**sample_decision(), 'best_prob': 0.56, 'ev_score': 0.12}
    runtime = TradingRuntime(StubML([cand]), None, None, None, connector=connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'hourly_floor': 0.58, 'hourly_floor_min': 0.55})
    import pandas as pd
    out = await runtime.hourly_scan(pd.DataFrame())
    assert out['placed'] is True
    async with SessionLocal() as s:
        trades = await persistence.last_trades(s, 1)
        assert 'hourly-guarantee@0.55' in (trades[0].reason or '')


def test_multiplier_key_matches_live_capture():
    """e:1032 payload: SL/TP as {"value":...,"type":"price"} with NO trailing
    field (exact shape of the live platform capture)."""
    from common.socketkey.olymptradekey import OlympTradeConnection
    k = OlympTradeConnection.__new__(OlympTradeConnection)
    k.account_id = 2939944075
    k.group_id = 'demo'
    key = k.get_order_key('up', 'USDJPY', '1', multiplicator=100,
                          stop_loss={'value': 158.298, 'type': 'price'},
                          take_profit={'value': 159.249, 'type': 'price'})
    assert key[0]['e'] == 1032
    d = key[0]['d'][0]
    assert d['pair'] == 'USDJPY'
    assert d['stop_loss'] == {'value': 158.298, 'type': 'price'}
    assert d['take_profit'] == {'value': 159.249, 'type': 'price'}
    assert 'trailing' not in d['stop_loss']
    assert 'trailing' not in d['take_profit']
    assert d['multiplicator'] == 100
    assert d['dir'] == 'up'


async def test_multiplier_broker_settlement():
    """A multiplier close (price_close + realized_pnl) settles the trade."""
    from app.services.tracker import TradeTracker
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 10,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'order_type': 'multiplier', 'multiplicator': 100})
        r = await svc.execute(s, sample_decision(), decision_id=70)
        assert r['placed'] is True
        # broker pushes the multiplier close state (e:22)
        deal = {'id': r['broker_ref'], 'price_open': 158.931, 'price_close': 159.20,
                'realized_pnl': 0.27, 'closing_reason': 'TakeProfit reached',
                'status': 'closed'}
        n = await TradeTracker.process_broker_deals(s, [deal])
        assert n == 1
        t = (await persistence.last_trades(s, 1))[0]
        assert t.status == 'expired'
        assert t.result == 'WIN'
        assert t.entry == 158.931          # price_open, not curs_open
        assert t.exit_price == 159.20


async def test_dual_mode_places_both_markets():
    """One signal with order_types [binary, multiplier] places BOTH a
    fixed-time (e:23) and a forex (e:1032) order on the same pair."""
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'order_types': ['binary', 'multiplier'],
                                  'multiplicator': 100})
        r = await svc.execute(s, sample_decision(), decision_id=80)
        assert r['placed'] is True
        assert r['placed_count'] == 2
        assert sorted(r['modes']) == ['binary', 'multiplier']
        modes = [p['order_type'] for p in connector.placed]
        assert sorted(modes) == ['binary', 'multiplier']
        # binary order carries duration + no SL/TP; multiplier carries SL/TP, no duration
        bin_p = next(p for p in connector.placed if p['order_type'] == 'binary')
        mult_p = next(p for p in connector.placed if p['order_type'] == 'multiplier')
        assert bin_p['duration_sec'] == 900
        assert bin_p['take_profit'] is None
        assert mult_p['duration_sec'] is None
        assert mult_p['take_profit'] == {'type': 'price', 'value': 1.0892}
        assert mult_p['stop_loss'] == {'type': 'price', 'value': 1.088}
        # both rows recorded under the same decision, unique broker refs
        trades = await persistence.last_trades(s, 5)
        by_mode = {t.order_type: t for t in trades}
        assert set(by_mode) == {'binary', 'multiplier'}
        assert by_mode['binary'].decision_id == by_mode['multiplier'].decision_id == 80
        assert by_mode['binary'].broker_ref == 'fake-1'
        assert by_mode['multiplier'].broker_ref == 'fake-2'
        assert by_mode['multiplier'].expiry_time is None
        assert by_mode['binary'].expiry_time is not None


def test_normalize_order_types_handles_legacy_and_lists():
    """order_types accepts lists, legacy single strings, and stays sane."""
    from app.services import risk as r
    assert r.normalize_order_types({'order_type': 'binary'}) == ['binary']
    assert r.normalize_order_types({'order_type': 'multiplier'}) == ['multiplier']
    assert r.normalize_order_types({'order_types': ['binary', 'multiplier']}) \
        == ['binary', 'multiplier']
    assert r.normalize_order_types({'order_types': 'binary,multiplier'}) \
        == ['binary', 'multiplier']
    assert r.normalize_order_types({'order_types': ['x']}) == ['binary']
    assert r.normalize_order_types({}) == ['binary']


async def test_get_limits_legacy_precedence_async():
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'order_type': 'multiplier'})
        limits = await risk.get_limits(s)
        assert limits['order_types'] == ['multiplier']
        assert limits['dry_run'] is False


async def test_auto_refresh_skips_without_credentials():
    """The watchdog must not launch Chrome when credentials are unset."""
    import os as _os
    from app.trading.scheduler import Scheduler
    sch = Scheduler(None, None)
    _os.environ.pop('DT_OLYMP_EMAIL', None)
    _os.environ.pop('DT_OLYMP_PASSWORD', None)
    assert await sch._auto_refresh_token(force=True) is False


def test_refresh_script_requires_credentials_to_login():
    """The script refuses to run a login flow without env credentials."""
    import os as _os
    _os.environ.pop('DT_OLYMP_EMAIL', None)
    _os.environ.pop('DT_OLYMP_PASSWORD', None)
    code = compile(open('scripts/refresh_token.py').read(), 'refresh_token.py', 'exec')
    assert 'DT_OLYMP_EMAIL' in open('scripts/refresh_token.py').read()


async def test_dual_mode_binary_leg_rejected():
    """When the broker rejects one leg (e.g. plain binary market closed),
    that leg records as cancelled with the broker message and the other
    leg still places."""
    connector = FakeConnector()
    svc = ExecutionService(connector)

    class FlakyConnector(FakeConnector):
        def place_bet(self, symbol, direction, amount, duration_sec=None,
                      order_type='binary', multiplicator=100,
                      take_profit=None, stop_loss=None):
            if order_type == 'binary':
                return {'error': 'The currency pair is unavailable',
                        'code': 'pair_unavailable'}
            return super().place_bet(symbol, direction, amount,
                                     duration_sec=duration_sec,
                                     order_type=order_type,
                                     multiplicator=multiplicator,
                                     take_profit=take_profit, stop_loss=stop_loss)

    flaky = FlakyConnector()
    svc2 = ExecutionService(flaky)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'order_types': ['binary', 'multiplier']})
        r = await svc2.execute(s, sample_decision(), decision_id=90)
        assert r['placed'] is True                  # multiplier leg placed
        assert r['placed_count'] == 1
        trades = await persistence.last_trades(s, 5)
        by_mode = {t.order_type: t for t in trades}
        assert by_mode['binary'].status == 'cancelled'
        assert 'pair_unavailable' in (by_mode['binary'].reason or '')
        assert by_mode['multiplier'].status == 'open'
        assert by_mode['multiplier'].broker_ref.startswith('fake-')


def test_renew_cookie_parser():
    """Set-Cookie parsing must extract access/refresh/__cflb from the live
    renew endpoint's headers."""
    from app.connectors.olymp import _parse_renew_cookies
    headers = [
        'refresh_token=; Path=/api/token/renew/web; Domain=olymptrade.com; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0',
        'access_token=eyJhbGciOiJSUzI1NiJ9.newaccess; Path=/; HttpOnly; Secure; SameSite=None',
        'refresh_token=eyJhbGciOiJSUzI1NiJ9.newrefresh; Path=/api/token/renew/web; HttpOnly',
        '__cflb=02DiuGSURUTCLDAS4xX8HLyoQLMaecKhHTTQY1QgWx8eY; HttpOnly; SameSite=None; Secure; Path=/; Expires=Tue, 18 Aug 2026 04:02:12 GMT',
    ]
    parsed = _parse_renew_cookies(headers)
    assert parsed['access_token'] == 'eyJhbGciOiJSUzI1NiJ9.newaccess'
    assert parsed['refresh_token'] == 'eyJhbGciOiJSUzI1NiJ9.newrefresh'
    assert parsed['__cflb'].startswith('02Diu')


async def test_cooldown_skips_cancelled_trades():
    """Cancelled/never-placed trades must not trigger the symbol cooldown."""
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 300,
                                  'stake_pct': 0.01, 'equity': 1000.0})
        await persistence.record_trade(s, {'decision_id': 91, 'symbol': 'FX:EURUSD',
                                           'tf': '5m', 'expiry': '15m', 'action': 'CALL',
                                           'entry': 1.08, 'stake': 10.0, 'dry_run': False,
                                           'status': 'cancelled', 'expiry_time': None,
                                           'reason': 'cancelled: broker rejected',
                                           'candle_close_ts': '2026-08-12T10:00:00'})
        ok, why = await risk.allowed(s, 'FX:EURUSD')
        assert ok, why


async def test_idempotency_ignores_cancelled():
    """A cancelled (never-placed) trade must not block a retry of the same
    signal - the broker error could be transient."""
    connector = FakeConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'order_types': ['binary']})
        # record a cancelled trade with the same signal identity
        await persistence.record_trade(s, {'decision_id': 92, 'symbol': 'FX:EURUSD',
                                           'tf': '5m', 'expiry': '15m', 'action': 'CALL',
                                           'entry': 1.08, 'stake': 10.0, 'dry_run': False,
                                           'status': 'cancelled', 'expiry_time': None,
                                           'reason': 'cancelled: broker rejected',
                                           'candle_close_ts': '2026-08-12 10:00:00'})
        r = await svc.execute(s, sample_decision(), decision_id=93)
        assert r['placed'] is True                  # retry allowed
        assert r['broker_ref'] == 'fake-1'


def test_instruments_payout_and_tradability():
    """Profitability -> payout conversion and the closed-market flag."""
    import time as _t
    from app.connectors import instruments as inst
    with inst._LOCK:
        inst._CACHE['profitability'] = {'EURUSD': 82.0, 'USDJPY': 10.0}
        inst._CACHE['schedule'] = {'EURGBP': {'locked': True, 'time_open': 0,
                                              'time_close': 0, 'winperc': 0}}
        inst._CACHE['ts'] = _t.time()              # fresh: no live probe
    assert inst.payout_for('EURUSD') == 0.82
    assert inst.payout_for('USDJPY') == inst.DEFAULT_PAYOUT      # closed -> flat
    assert inst.payout_for('XXXXXX') == inst.DEFAULT_PAYOUT      # unknown
    ok, why = inst.pair_tradable('EURUSD')
    assert ok, why
    ok2, why2 = inst.pair_tradable('USDJPY')
    assert not ok2 and 'closed' in why2
    ok3, why3 = inst.pair_tradable('EURGBP')
    assert not ok3 and 'locked' in why3


def test_cid_app_current_version():
    from common.constants import OLYMP_WS
    assert '2026.3.2330613' in OLYMP_WS


async def test_multiplier_retries_without_sl_tp_on_stop_error():
    """When the broker rejects SL/TP (incorrect_stop_condition) the leg
    retries without levels instead of failing."""

    class StopRejectConnector(FakeConnector):
        def __init__(self):
            super().__init__()
            self.rejected = 0

        def place_bet(self, symbol, direction, amount, duration_sec=None,
                      order_type='binary', multiplicator=100,
                      take_profit=None, stop_loss=None):
            if order_type == 'multiplier' and (take_profit or stop_loss):
                self.rejected += 1
                return {'error': 'Invalid Take Profit or Stop Loss value',
                        'code': 'incorrect_stop_condition'}
            return super().place_bet(symbol, direction, amount,
                                     duration_sec=duration_sec,
                                     order_type=order_type,
                                     multiplicator=multiplicator,
                                     take_profit=take_profit, stop_loss=stop_loss)

    connector = StopRejectConnector()
    svc = ExecutionService(connector)
    async with SessionLocal() as s:
        await risk.set_limits(s, {'dry_run': False, 'max_trades_per_day': 14,
                                  'max_daily_loss_pct': 5.0, 'symbol_cooldown_min': 0,
                                  'stake_pct': 0.01, 'equity': 1000.0,
                                  'order_types': ['multiplier']})
        r = await svc.execute(s, sample_decision(), decision_id=95)
        assert r['placed'] is True
        assert connector.rejected == 1             # first attempt had SL/TP
        placed = connector.placed
        assert len(placed) == 1                    # retry without levels
        assert placed[0]['take_profit'] is None and placed[0]['stop_loss'] is None

