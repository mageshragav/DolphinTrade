"""Live instrument intelligence from the broker websocket.

The platform's real payouts and tradability are published as subscriptions:
- profitability list (pair -> winperc %; pairs with value ~10 are currently
  CLOSED on the digital market) - resource batch [74,301,73,4074,4301,4076]
- instrument schedule (locked / time_open / time_close) - e:182 by account

Results are cached in-memory (TTL) so the hot paths (EV gating, order
placement) do a plain dict lookup.
"""

import json
import logging
import threading
import time

from common.constants import HEADERS, OLYMP_WS, OLYMP_ORIGIN, OLYMP_EXTENSIONS

LOGGER = logging.getLogger('dolphin')

PROFIT_BATCH = [{"t": 2, "e": 98, "d": [74, 301, 73, 4074, 4301, 4076]}]
TTL = 600.0            # refresh instrument data every 10 min
MIN_TRADABLE = 50.0    # profitability below this = market closed
DEFAULT_PAYOUT = 0.90

_LOCK = threading.Lock()
_CACHE = {
    'ts': 0.0,
    'profitability': {},      # pair -> pct
    'schedule': {},           # pair -> {locked, time_open, time_close, winperc}
}


def _probe():
    """Open a short websocket, subscribe like the browser, harvest the
    profitability + schedule payloads, close. Returns (profit, schedule)."""
    from websocket import create_connection
    from common.socketkey.olymptradekey import OlympTradeConnection
    profit, schedule = {}, {}
    key = OlympTradeConnection(group='demo')
    ws = create_connection(OLYMP_WS, header=HEADERS, origin=OLYMP_ORIGIN,
                           extensions=OLYMP_EXTENSIONS, timeout=20)
    try:
        ws.send(json.dumps(PROFIT_BATCH))
        ws.send(json.dumps([
            {"t": 2, "e": 182, "uuid": "INST1820001",
             "d": [{"account_id": key.account_id}]}]))
        ws.settimeout(2)
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                raw = ws.recv()
            except Exception:
                break
            if not raw:
                continue
            try:
                msgs = json.loads(raw)
            except Exception:
                continue
            for m in (msgs if isinstance(msgs, list) else [msgs]):
                d = m.get('d')
                if isinstance(d, list):
                    for item in d:
                        if isinstance(item, dict) and item.get('pair') \
                                and 'profitability' in item:
                            profit[item['pair']] = float(item['profitability'])
                        if isinstance(item, dict) and item.get('id') \
                                and 'locked' in item:
                            schedule[item['id']] = {
                                'locked': bool(item.get('locked')),
                                'locked_trading': bool(item.get('locked_trading')),
                                'time_open': item.get('time_open') or 0,
                                'time_close': item.get('time_close') or 0,
                                'winperc': item.get('winperc') or 0,
                            }
    finally:
        try:
            ws.close()
        except Exception:
            pass
    return profit, schedule


def refresh(force=False):
    """Re-probe and refresh the cache (thread-safe)."""
    with _LOCK:
        if not force and time.time() - _CACHE['ts'] < TTL:
            return True
    try:
        profit, schedule = _probe()
        with _LOCK:
            if profit or schedule:
                _CACHE['profitability'] = profit or _CACHE['profitability']
                _CACHE['schedule'] = schedule or _CACHE['schedule']
                _CACHE['ts'] = time.time()
        LOGGER.info(f'instruments: {len(profit)} payouts, '
                    f'{len(schedule)} schedule entries')
        return bool(profit or schedule)
    except Exception as e:
        LOGGER.warning(f'instrument probe failed: {e}')
        return False


def _ensure():
    if time.time() - _CACHE['ts'] > TTL:
        refresh()


def profitability(pair: str) -> float | None:
    """winperc % for the pair (None when unknown). ~10 marks a closed market."""
    _ensure()
    with _LOCK:
        return _CACHE['profitability'].get(pair)


def payout_for(pair: str) -> float:
    """Fractional payout for EV calculations (default 0.90 when unknown)."""
    p = profitability(pair)
    if p is None or p < MIN_TRADABLE:
        return DEFAULT_PAYOUT
    return p / 100.0


def pair_tradable(pair: str) -> tuple[bool, str]:
    """Is the pair tradable right now on the digital market?

    Returns (ok, reason). Uses the live profitability flag and the broker's
    published schedule window when available. With no cached data yet the
    pair is allowed through (fallback = previous behavior).
    """
    _ensure()
    with _LOCK:
        prof = _CACHE['profitability'].get(pair)
        sch = _CACHE['schedule'].get(pair)
        have_data = bool(_CACHE['profitability']) or bool(_CACHE['schedule'])
    if not have_data:
        return True, 'ok (no instrument data yet)'
    if prof is not None and prof < MIN_TRADABLE:
        return False, f'market closed (profitability {prof:.0f}%)'
    if sch:
        if sch['locked']:
            return False, 'market closed (schedule: locked)'
        now = time.time()
        if sch['time_open'] and sch['time_close'] and sch['time_open'] > now:
            return False, 'market closed (opens later)'
    return True, 'ok'


def snapshot() -> dict:
    _ensure()
    with _LOCK:
        return {
            'ts': _CACHE['ts'],
            'profitability': dict(_CACHE['profitability']),
            'schedule': dict(_CACHE['schedule']),
        }
