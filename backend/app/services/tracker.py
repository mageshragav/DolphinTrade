"""Trade lifecycle: settle open trades at expiry against the feed, broker
P&L sync (when available), and the circuit-breaker drift computation."""

import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, ws
from app.services import persistence, risk

LOGGER = logging.getLogger('dolphin')


class TradeTracker:
    @staticmethod
    async def process_broker_deals(session: AsyncSession, deals: list[dict]) -> int:
        """Settle trades from broker deal states (e:22 pushes / e:31 poll).

        A deal is settled when the broker reports a close: balance_change != 0,
        or curs_close != 0, or a terminal status. Works for binary AND
        multiplier trades (multiplier has no expiry_time - only the broker
        knows when it closes).
        """
        updated = 0
        for deal in deals:
            ref = str(deal.get('id', ''))
            if not ref:
                continue
            q = select(models.Trade).where(models.Trade.broker_ref == ref)
            t = (await session.execute(q)).scalars().first()
            if t is None:
                continue
            changed = False
            if (deal.get('curs_open') or deal.get('price_open')) and not t.entry:
                t.entry = float(deal.get('curs_open') or deal.get('price_open'))
                changed = True
            if deal.get('winperc') and not t.winperc:
                t.winperc = float(deal['winperc'])
                changed = True
            if deal.get('time_close_default') and not t.expiry_time:
                t.expiry_time = datetime.fromtimestamp(
                    float(deal['time_close_default']), tz=timezone.utc)
                changed = True
            if deal.get('status') and deal['status'] != t.broker_status:
                t.broker_status = str(deal['status'])
                changed = True

            balance_change = deal.get('balance_change') or 0
            curs_close = deal.get('curs_close') or 0
            price_close = deal.get('price_close') or 0
            realized_pnl = deal.get('realized_pnl')
            closing_reason = deal.get('closing_reason') or ''
            terminal = deal.get('status') in ('won', 'lost', 'closed', 'settled')
            # multiplier closes are reported via price_close / realized_pnl /
            # closing_reason instead of balance_change/curs_close
            mult_closed = price_close != 0 or closing_reason or realized_pnl is not None
            exit_p = None
            if t.status == 'open' and (terminal or balance_change != 0 or curs_close != 0
                                       or mult_closed):
                if realized_pnl is not None:
                    result = ('WIN' if realized_pnl > 0
                              else 'LOSS' if realized_pnl < 0 else 'DRAW')
                    exit_p = float(price_close) if price_close else t.entry
                elif balance_change != 0:
                    result = 'WIN' if balance_change > 0 else 'LOSS'
                elif curs_close != 0 and t.entry:
                    up = (t.action == 'CALL')
                    result = 'WIN' if (curs_close > t.entry) == up and curs_close != t.entry \
                        else ('DRAW' if curs_close == t.entry else 'LOSS')
                elif terminal:
                    result = 'WIN' if deal.get('status') == 'won' else 'LOSS'
                else:
                    result = None
                if result:
                    t.status = 'expired'
                    t.result = result
                    if exit_p:
                        t.exit_price = round(float(exit_p), 5)
                    elif curs_close:
                        t.exit_price = float(curs_close)
                    changed = True
                    await ws.broadcast({'type': 'trade_settled', 'trade': {
                        'id': t.id, 'symbol': t.symbol, 'action': t.action,
                        'result': result, 'exit_price': t.exit_price}})
                    LOGGER.info(f'broker-settled {t.symbol} {t.action} -> {result}')
            if changed:
                await session.commit()
                updated += 1
        return updated

    @staticmethod
    async def settle(session: AsyncSession, candles: pd.DataFrame):
        """Settle open trades whose expiry time has passed, using the feed."""
        q = select(models.Trade).where(models.Trade.status == 'open')
        open_trades = list((await session.execute(q)).scalars().all())
        if not open_trades or candles is None or candles.empty:
            return []

        cd = candles.copy()
        if 'o' in cd.columns:
            cd = cd.rename(columns={'o': 'open', 'h': 'high', 'l': 'low',
                                    'c': 'close', 'v': 'volume'})
        if 'datetime' not in cd.columns and 't' in cd.columns:
            cd['datetime'] = pd.to_datetime(cd['t'], unit='s', utc=True)
        cd['datetime'] = pd.to_datetime(cd['datetime'])
        if cd['datetime'].dt.tz is not None:
            cd['datetime'] = cd['datetime'].dt.tz_localize(None)
        closes = {}
        for sym, grp in cd.groupby('symbol'):
            # same symbol convention as trades: plain or _OTC names normalize
            # to 'FX:<NAME>' so the lookup can never miss
            name = str(sym).replace('_OTC', '')
            if not name.startswith('FX:'):
                name = 'FX:' + name
            g = grp.sort_values('datetime')
            closes[name] = dict(zip(g['datetime'].values, g['close'].values))

        now = datetime.now(timezone.utc)
        settled = []
        for t in open_trades:
            exp = t.expiry_time
            if exp is None or exp.replace(tzinfo=timezone.utc) > now:
                continue
            sym = t.symbol
            closes_map = closes.get(sym)
            if not closes_map:
                continue
            best = next((c for ts, c in sorted(closes_map.items())
                         if pd.Timestamp(ts) >= exp.replace(tzinfo=None)), None)
            if best is None:
                continue
            entry = float(t.entry)
            exit_p = float(best)
            if t.action == 'CALL':
                result = 'WIN' if exit_p > entry else ('LOSS' if exit_p < entry else 'DRAW')
            else:
                result = 'WIN' if exit_p < entry else ('LOSS' if exit_p > entry else 'DRAW')
            await persistence.update_trade(session, t.id, status='expired',
                                           exit_price=round(exit_p, 5), result=result)
            settled.append({'id': t.id, 'symbol': sym, 'action': t.action, 'result': result,
                            'exit_price': round(exit_p, 5)})
            await ws.broadcast({'type': 'trade_settled', 'trade': settled[-1]})
            LOGGER.info(f'settled {sym} {t.action} -> {result} at {exit_p:.5f}')
        return settled

    @staticmethod
    async def sync_broker_results(session: AsyncSession, connector) -> int:
        """Pull real broker results when the API reports history (best-effort)."""
        try:
            history = connector.client.get_history()
        except Exception as e:
            LOGGER.debug(f'broker history sync unavailable: {e}')
            return 0
        if not isinstance(history, list):
            return 0
        updated = 0
        for item in history:
            ref = str(item.get('id', ''))
            if not ref:
                continue
            q = select(models.Trade).where(models.Trade.broker_ref == ref,
                                           models.Trade.status == 'open')
            t = (await session.execute(q)).scalars().first()
            if t is None:
                continue
            result = 'WIN' if item.get('win') else ('LOSS' if item.get('lose') else 'DRAW')
            await persistence.update_trade(session, t.id, status='expired',
                                           result=result, exit_price=item.get('close_price'))
            updated += 1
        return updated

    @staticmethod
    async def refresh_circuit_breaker(session: AsyncSession, projected: float = 0.65):
        stats = await risk.circuit_breaker_status(session)
        await persistence.set_setting(session, risk.KEY_DRIFT,
                                      {**stats, 'projected': projected})
        if stats.get('paused'):
            await ws.broadcast({'type': 'alert',
                                'message': f'CIRCUIT BREAKER: win rate {stats["win_rate"]} '
                                           f'vs projected {projected} - consider pausing'})
        return stats
