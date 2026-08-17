"""Trading runtime: fetches candles, precomputes market candidates, runs
the LangGraph workflow per candidate, settles trades, refreshes the
circuit breaker, and broadcasts events."""

import asyncio
import logging
from datetime import datetime, timezone

from app import ws
from app.config import get_settings
from app.db import SessionLocal
from app.services import persistence, tracker
from app.services.execution import ExecutionService
from app.trading import graph as graph_mod

LOGGER = logging.getLogger('dolphin')


class TradingRuntime:
    def __init__(self, ml_service, news_agent, headline_agent, risk_agent,
                 connector=None, combos=None):
        self.ml = ml_service
        self.news = news_agent
        self.headlines = headline_agent
        self.risk = risk_agent
        self.connector = connector
        self.combos = combos or []
        self.executor = ExecutionService(connector=connector)
        self.graph = graph_mod.build_graph()
        self.running = False

    def set_combos(self, combos):
        self.combos = combos

    async def cycle(self, candles, history=None):
        """One decision cycle over all (symbol, combo) candidates."""
        if candles is None or candles.empty:
            return
        from app.trading.scheduler import parse_combos
        settings = get_settings()
        combos = self.combos or parse_combos(settings.combos)

        # 1. market candidates (one heavy feature/ML pass)
        decisions = self.ml.decide_all(candles, combos=combos)
        candidates = {}
        for d in decisions:
            candidates[(d['symbol'], d['tf'], d['expiry'])] = d
        candle_map = {sym: grp for sym, grp in candles.groupby('symbol')}

        graph_mod.set_context(
            candidates=candidates,
            candles=candle_map,
            news_agent=self.news,
            headline_agent=self.headlines,
            risk_agent=self.risk,
            theta=self.ml.theta if hasattr(self.ml, 'theta') else settings.theta,
            executor=self.executor,
        )

        # 2. run the workflow per candidate (below-gate candidates route to
        #    neutral immediately - the graph handles that)
        results = []
        for key, cand in candidates.items():
            symbol, tf, exp = key
            state = {'symbol': symbol, 'tf': tf, 'expiry': exp,
                     'candles_key': symbol, 'candidate': cand}
            try:
                out = await self.graph.ainvoke(state)
                if out.get('execution'):
                    results.append(out['execution'])
            except Exception as e:
                LOGGER.exception(f'graph failed for {symbol} {tf} {exp}: {e}')

        # 3. settle expired trades + circuit breaker
        async with SessionLocal() as session:
            await tracker.TradeTracker.settle(session, history if history is not None else candles)
            await tracker.TradeTracker.refresh_circuit_breaker(session)

        # 3b. broker-driven settlement (e:22 deal states from the order channel)
        if self.connector is not None and getattr(self.connector, 'channel', None):
            deals = self.connector.channel.deal_states()
            if deals:
                async with SessionLocal() as session:
                    await tracker.TradeTracker.process_broker_deals(session, deals)

        # 4. agent heartbeat
        await ws.broadcast({'type': 'agent', 'line': f'cycle complete '
                                                     f'{datetime.now(timezone.utc):%H:%M:%S} UTC',
                            'ts': datetime.now(timezone.utc).timestamp()})
        return results

    # -- feed helpers -------------------------------------------------------

    async def fetch_candles(self, feed):
        settings = get_settings()
        pairs = [p.strip() for p in settings.pairs.split(',') if p.strip()]
        df = await asyncio.to_thread(feed.fetch_candles, pairs, 600)
        if df is not None and not df.empty:
            try:
                async with SessionLocal() as session:
                    n = await persistence.archive_candles(session, df)
                if n:
                    LOGGER.debug(f'candle archive: +{n} bars')
            except Exception as e:
                LOGGER.warning(f'candle archive failed: {e}')
        return df

    async def refresh_agents(self, pairs):
        try:
            await asyncio.to_thread(self.news.refresh)
        except Exception as e:
            LOGGER.warning(f'news refresh failed: {e}')
        try:
            await asyncio.to_thread(self.headlines.refresh, pairs)
        except Exception as e:
            LOGGER.warning(f'headline refresh failed: {e}')

    async def hourly_scan(self, candles) -> dict:
        """Hourly minimum-signal guarantee.

        If the current UTC hour has no non-cancelled trade, scan the freshest
        candidates across all (symbol x combo), pick the highest-EV one whose
        best_prob >= hourly_floor and that passes every risk gate (cooldown
        aware), and place it. When nothing qualifies, still record + broadcast
        the best available candidate as an informational signal.
        """
        from app.trading.scheduler import parse_combos
        from app.services import risk as risk_svc
        settings = get_settings()
        combos = self.combos or parse_combos(settings.combos)
        now = datetime.now(timezone.utc)
        hour_key = now.strftime('%Y%m%d%H')

        # evaluate down to the fallback floor so sub-0.65 candidates are
        # visible to the picker (the normal gate stays at self.theta)
        decisions = self.ml.decide_all(candles, combos=combos, theta=0.55)
        async with SessionLocal() as session:
            if await persistence.trades_in_hour(session, hour_key):
                return {'scanned': False, 'reason': 'hour already traded'}
            limits = await risk_svc.get_limits(session)
            floor = float(limits.get('hourly_floor', 0.58))
            floor_min = float(limits.get('hourly_floor_min', 0.55))
            tiers = sorted({floor, floor_min}, reverse=True)

            picked, skipped = None, []
            used_tier = None
            for tier in tiers:
                cands = [d for d in decisions
                         if d['action'] in ('CALL', 'PUT')
                         and (d.get('best_prob') or 0.0) >= tier
                         and (d.get('ev_score') or 0.0) > 0.0]
                cands.sort(key=lambda d: d.get('ev_score') or 0.0, reverse=True)
                for d in cands:
                    ok, why = await risk_svc.allowed(session, d['symbol'],
                                                     combo_key=risk_svc.combo_key(d))
                    if ok:
                        picked, used_tier = d, tier
                        break
                    skipped.append(f"{d['symbol'].replace('FX:', '')}: {why}")
                if picked is not None:
                    break

            if picked is not None:
                picked['rationale'] = (picked.get('rationale') or '') + \
                    f' | hourly-guarantee (tier {used_tier:.2f})'
                picked['_reason_tag'] = f'hourly-guarantee@{used_tier:.2f}'
                row = await persistence.record_decision(session, picked)
                result = await self.executor.execute(session, picked,
                                                     decision_id=row.id)
                await ws.broadcast({'type': 'decision', **picked,
                                    'ts': now.isoformat()})
                LOGGER.info(f'hourly-guarantee: picked {picked["symbol"]} '
                            f'{picked["action"]} p={picked.get("best_prob"):.3f} '
                            f'-> {result}')
                return {'scanned': True, 'placed': result.get('placed'),
                        'symbol': picked['symbol'], 'action': picked['action'],
                        'reason': result.get('reason', '')}

            # informational signal: best candidate above the lowest tier, or
            # the overall best when nothing cleared it
            best = max(decisions, key=lambda d: d.get('best_prob') or 0.0)
            info = dict(best)
            info.update({
                'symbol': best.get('symbol', 'ALL'),
                'tf': best.get('tf', '5m'),
                'expiry': best.get('expiry', '1h'),
                'action': 'NEUTRAL',
                'best_prob': best.get('best_prob', 0.0),
                'rationale': 'hourly-scan: ' + (
                    f'best {info.get("best_prob", 0):.3f} < '
                    f'lowest tier {min(tiers):.2f}'
                    if (best.get('best_prob') or 0) < min(tiers) else
                    'best candidate blocked by risk gates') +
                    (f'; blocked: {"; ".join(skipped[:3])}' if skipped else ''),
            })
            row = await persistence.record_decision(session, info)
            await ws.broadcast({'type': 'decision', **info, 'ts': now.isoformat()})
            LOGGER.info(f'hourly-scan: no trade - {info["rationale"]}')
            return {'scanned': True, 'placed': False, 'symbol': info['symbol'],
                    'reason': info['rationale'], 'decision_id': row.id}
