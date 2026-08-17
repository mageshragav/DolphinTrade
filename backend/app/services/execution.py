"""Trade execution: idempotency check -> risk gates -> place bets -> record.

Every signal flows through here and can trade BOTH markets at once: each
enabled order type ('binary' fixed-time e:23 and/or 'multiplier' forex e:1032)
places its own order on the same pair/direction and records its own trade row
under the same decision. Dry-run records without placing.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app import ws
from app.connectors.olymp import OlympConnector
from app.services import persistence, risk

LOGGER = logging.getLogger('dolphin')


def expiry_datetime(candle_close: str, expiry: str) -> datetime:
    try:
        ts = datetime.fromisoformat(candle_close)
    except Exception:
        ts = datetime.now(timezone.utc)
    if expiry.endswith('h'):
        return ts + timedelta(hours=int(expiry[:-1]))
    return ts + timedelta(minutes=int(expiry.rstrip('m')))


class ExecutionService:
    def __init__(self, connector: OlympConnector | None = None):
        self.connector = connector

    @staticmethod
    def _build_sl_tp(d: dict, limits: dict) -> tuple[dict | None, dict | None]:
        """Multiplier SL/TP from signal levels, or ATR-scaled in 'atr' mode."""
        sl_tp_mode = limits.get('sl_tp_mode', 'signal_levels')
        if sl_tp_mode == 'atr' and d.get('atr'):
            sign = 1.0 if d['action'] == 'CALL' else -1.0
            atr = float(d['atr'])
            tp = {'type': 'price',
                  'value': round(d.get('entry_price', 0) + sign * float(
                      limits.get('atr_tp_mult', 3.0)) * atr, 5)}
            sl = {'type': 'price',
                  'value': round(d.get('entry_price', 0) - sign * float(
                      limits.get('atr_sl_mult', 1.5)) * atr, 5)}
            return tp, sl
        tp = {'type': 'price', 'value': float(d['target_price'])} if d.get('target_price') else None
        sl = {'type': 'price', 'value': float(d['stop_loss'])} if d.get('stop_loss') else None
        return tp, sl

    async def _place_one(self, session, d: dict, decision_id: int, mode: str,
                         limits: dict, stake: float, dry_run: bool, ok: bool,
                         why: str) -> dict:
        """Place (or record) a single order of `mode` and persist its trade."""
        reason_tag = d.get('_reason_tag', '')
        trade = {
            'decision_id': decision_id,
            'symbol': d['symbol'], 'tf': d.get('tf', '5m'), 'expiry': d.get('expiry', '15m'),
            'action': d['action'],
            'candle_open': d.get('candle_open'), 'candle_close': d.get('candle_close_price'),
            'entry': d.get('entry_price'), 'take_profit': d.get('target_price'),
            'stop_loss': d.get('stop_loss'),
            'expiry_time': None if mode == 'multiplier' else
            expiry_datetime(d.get('candle_close', ''), d.get('expiry', '15m')),
            'candle_close_ts': d.get('candle_close', ''),
            'stake': stake,
            'dry_run': dry_run,
            'order_type': mode,
        }
        placed = False
        if dry_run:
            trade['status'] = 'open'
            trade['reason'] = f'dry-run ({mode})' + \
                (f' | {reason_tag}' if reason_tag else '')
            placed = True
        elif ok:
            try:
                if mode == 'binary':
                    # availability pre-check: the digital market runs on a
                    # schedule - don't even send the order when it's closed
                    from app.connectors import instruments
                    tradable, why = instruments.pair_tradable(
                        d['symbol'].split(':')[-1])
                    if not tradable:
                        raise RuntimeError(why)
                tp = sl = None
                if mode == 'multiplier':
                    tp, sl = self._build_sl_tp(d, limits)
                    duration = None
                else:
                    duration = int(d['expiry'].rstrip('m')) * 60 if d['expiry'].endswith('m') \
                        else int(d['expiry'].rstrip('h')) * 3600
                deal = self.connector.place_bet(
                    d['symbol'], 'up' if d['action'] == 'CALL' else 'down',
                    trade['stake'], duration_sec=duration, order_type=mode,
                    multiplicator=limits.get('multiplicator', 100),
                    take_profit=tp, stop_loss=sl)
                if isinstance(deal, dict) and deal.get('error'):
                    # broker rejected this leg (e.g. market closed) - fail it
                    if mode == 'multiplier' and (tp or sl) and \
                            'stop' in str(deal.get('code', '')).lower():
                        # SL/TP too tight for the broker's rules - retry
                        # without levels (broker applies its own defaults)
                        LOGGER.info(f'multiplier SL/TP rejected '
                                    f'({deal.get("code")}) - retrying without levels')
                        deal = self.connector.place_bet(
                            d['symbol'], 'up' if d['action'] == 'CALL' else 'down',
                            trade['stake'], duration_sec=None, order_type=mode,
                            multiplicator=limits.get('multiplicator', 100),
                            take_profit=None, stop_loss=None)
                    if isinstance(deal, dict) and deal.get('error'):
                        raise RuntimeError(f"{deal.get('code', '')}: {deal['error']}")
                trade['status'] = 'open'
                trade['broker_ref'] = str(deal.get('id', '')) if isinstance(deal, dict) else str(deal)
                if isinstance(deal, dict):
                    if deal.get('curs_open') or deal.get('price_open'):
                        trade['entry'] = float(deal.get('curs_open')
                                               or deal.get('price_open'))
                    if mode == 'binary' and deal.get('time_close_default'):
                        trade['expiry_time'] = datetime.fromtimestamp(
                            float(deal['time_close_default']), tz=timezone.utc)
                    trade['winperc'] = deal.get('winperc')
                    trade['broker_status'] = deal.get('status')
                trade['placed_ts'] = datetime.now(timezone.utc)
                trade['reason'] = f'placed ({mode})' + \
                    (f' | {reason_tag}' if reason_tag else '')
                placed = True
            except Exception as e:
                trade['status'] = 'cancelled'
                trade['reason'] = f'broker error: {e}'
                LOGGER.error(f'bet failed {d["symbol"]} {d["action"]} ({mode}): {e}')
        else:
            trade['status'] = 'cancelled'
            trade['reason'] = why

        row = await persistence.record_trade(session, trade)
        await ws.broadcast({'type': 'trade', 'trade': {
            'id': row.id, 'symbol': row.symbol, 'tf': row.tf, 'expiry': row.expiry,
            'action': row.action, 'entry': row.entry, 'take_profit': row.take_profit,
            'stop_loss': row.stop_loss, 'expiry_time': str(row.expiry_time),
            'status': row.status, 'result': row.result, 'exit_price': row.exit_price,
            'dry_run': row.dry_run, 'reason': row.reason}})
        return {'mode': mode, 'placed': placed, 'reason': trade['reason'],
                'trade_id': row.id, 'broker_ref': trade.get('broker_ref')}

    async def execute(self, session: AsyncSession, d: dict, decision_id: int) -> dict:
        """Run the full execution pipeline for a CALL/PUT decision.

        Places one order per enabled mode (binary fixed-time + multiplier
        forex) on the same pair and direction.
        """
        limits = await risk.get_limits(session)
        modes = risk.normalize_order_types(limits)
        dry_run = limits.get('dry_run', True)
        ok, why = await risk.allowed(session, d['symbol'])

        # per-mode idempotency: the same signal may trade both markets, but
        # each market only once
        for mode in modes:
            if await persistence.trade_exists(session, d['symbol'], d.get('candle_close', ''),
                                              d['action'], d.get('expiry', '15m'),
                                              order_type=mode):
                return {'placed': False, 'reason': f'duplicate signal (idempotency: {mode})'}

        base_stake = round(limits.get('equity', 1000.0) * limits.get('stake_pct', 0.01), 2)
        stake = await risk.stake_for(session, base_stake, limits)

        results = []
        for mode in modes:
            results.append(await self._place_one(session, d, decision_id, mode,
                                                 limits, stake, dry_run, ok, why))

        placed_any = any(r['placed'] for r in results)
        first = results[0] if results else {}
        return {
            'placed': placed_any,
            'placed_count': sum(1 for r in results if r['placed']),
            'modes': [r['mode'] for r in results],
            'reason': ', '.join(r['reason'] for r in results),
            'dry_run': dry_run,
            'results': results,
            'broker_ref': first.get('broker_ref'),
            'trade_id': first.get('trade_id'),
        }
