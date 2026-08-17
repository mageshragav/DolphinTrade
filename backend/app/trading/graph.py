"""LangGraph multi-agent workflow.

One invocation = one candidate (symbol + combo). The runtime precomputes
market candidates (expensive feature/ML step) once per cycle and registers
them; nodes read from the registry. News/headline/risk run in parallel and
join at the orchestrator. Below-gate candidates skip the LLM/risk agents
entirely (latency + cost optimization).
"""

import logging
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app import ws
from app.db import SessionLocal
from app.services import persistence
from app.services.execution import ExecutionService

LOGGER = logging.getLogger('dolphin')

THETA = 0.65


class TradeState(TypedDict, total=False):
    symbol: str
    tf: str
    expiry: str
    candles_key: str
    candidate: dict            # market result for this symbol/combo
    news: dict                 # veto, fired events
    sentiment: dict            # bias, headline
    risk: dict                 # manipulation flags
    decision: dict             # final decision payload
    execution: dict            # execution result


# runtime-provided context (set per cycle)
CTX = {
    'candidates': {},          # (symbol, tf, expiry) -> candidate dict
    'candles': {},             # symbol -> candles frame
    'news_agent': None,
    'headline_agent': None,
    'risk_agent': None,
    'theta': THETA,
    'executor': None,
}


def set_context(**kwargs):
    CTX.update(kwargs)


# ---------------------------------------------------------------------------
# nodes
# ---------------------------------------------------------------------------

async def market_node(state: TradeState):
    key = (state['symbol'], state['tf'], state['expiry'])
    candidate = CTX['candidates'].get(key)
    if candidate is None:
        return {'candidate': {'action': 'NEUTRAL', 'best_prob': 0.0, 'ev_score': 0.0,
                              'rationale': 'no market candidate'}}
    return {'candidate': candidate}


async def news_node(state: TradeState):
    agent = CTX['news_agent']
    if agent is None:
        return {'news': {'veto': False, 'event': None}}
    blackout = 0
    try:
        from app.services import risk
        async with SessionLocal() as s:
            blackout = float((await risk.get_limits(s)).get('news_blackout_min', 0) or 0)
    except Exception:
        pass
    veto, evt = agent.veto(symbol=state['symbol'], blackout_min=blackout)
    return {'news': {'veto': bool(veto), 'event': evt}}


async def headline_node(state: TradeState):
    agent = CTX['headline_agent']
    if agent is None:
        return {'sentiment': {'bias': 'neutral', 'headline': None}}
    return {'sentiment': {'bias': agent.bias(state['symbol']),
                          'headline': agent.top(state['symbol'])}}


async def risk_node(state: TradeState):
    agent = CTX['risk_agent']
    if agent is None:
        return {'risk': {'manipulation_risk': 'low', 'flags': []}}
    candles = CTX['candles'].get(state['symbol'])
    if candles is None or candles.empty:
        return {'risk': {'manipulation_risk': 'low', 'flags': []}}
    return {'risk': agent.analyze(candles).get(state['symbol'],
                                               {'manipulation_risk': 'low', 'flags': []})}


async def orchestrator_node(state: TradeState):
    c = state['candidate']
    news = state.get('news', {})
    sentiment = state.get('sentiment', {})
    risk = state.get('risk', {})
    veto = bool(news.get('veto'))
    risk_high = risk.get('manipulation_risk') == 'high'
    ev = c.get('ev_score', 0.0)
    best = c.get('best_prob', 0.0)
    action = c.get('action', 'NEUTRAL')
    if veto or risk_high or ev <= 0.0 or best < CTX['theta']:
        action = 'NEUTRAL'
        reasons = []
        if veto:
            reasons.append(f"news veto: {(news.get('event') or {}).get('title', '')}")
        if risk_high:
            reasons.append('risk high')
        if ev <= 0.0:
            reasons.append('negative EV')
        if best < CTX['theta']:
            reasons.append('below gate')
        c = {**c, 'action': 'NEUTRAL',
             'rationale': c.get('rationale', '') + ' | ' + '; '.join(reasons)}
    c = {**c,
         'sentiment_bias': sentiment.get('bias', 'neutral'),
         'headline': sentiment.get('headline'),
         'manipulation_risk': risk.get('manipulation_risk', 'low'),
         'news_veto': veto,
         'news_next': (news.get('event') or {}).get('title') if veto else None}
    return {'decision': c}


async def execution_node(state: TradeState):
    d = state['decision']
    async with SessionLocal() as session:
        row = await persistence.record_decision(session, d)
        executor = CTX.get('executor') or ExecutionService()
        result = await executor.execute(session, d, decision_id=row.id)
    await ws.broadcast({'type': 'decision', **d, 'ts': datetime.now(timezone.utc).isoformat()})
    return {'execution': result}


async def neutral_node(state: TradeState):
    d = state.get('decision')
    if d is None:
        # routed to neutral before the orchestrator (below gate)
        c = state.get('candidate', {})
        d = {**c, 'action': 'NEUTRAL',
             'rationale': c.get('rationale', 'below gate'),
             'sentiment_bias': 'neutral', 'manipulation_risk': 'low',
             'news_veto': False, 'news_next': None, 'headline': None}
    async with SessionLocal() as session:
        row = await persistence.record_decision(session, d)
    await ws.broadcast({'type': 'decision', **d, 'ts': datetime.now(timezone.utc).isoformat()})
    return {'execution': {'placed': False, 'reason': 'neutral'}}


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------

def route_after_market(state: TradeState):
    c = state.get('candidate', {})
    if c.get('best_prob', 0.0) >= CTX['theta']:
        return 'continue'
    return 'neutral'


def route_after_orchestrator(state: TradeState):
    d = state.get('decision', {})
    if d.get('action') in ('CALL', 'PUT'):
        return 'execute'
    return 'neutral'


def build_graph():
    g = StateGraph(TradeState)
    g.add_node('market', market_node)
    g.add_node('news', news_node)
    g.add_node('headline', headline_node)
    g.add_node('risk', risk_node)
    g.add_node('orchestrator', orchestrator_node)
    g.add_node('execution', execution_node)
    g.add_node('neutral', neutral_node)

    g.add_edge(START, 'market')
    g.add_conditional_edges('market', route_after_market,
                            {'continue': 'news', 'neutral': 'neutral'})
    # parallel fan-out after market (all three agents run concurrently)
    g.add_edge('news', 'orchestrator')
    g.add_edge('headline', 'orchestrator')
    g.add_edge('risk', 'orchestrator')
    g.add_conditional_edges('orchestrator', route_after_orchestrator,
                            {'execute': 'execution', 'neutral': 'neutral'})
    g.add_edge('execution', END)
    g.add_edge('neutral', END)
    return g.compile()
