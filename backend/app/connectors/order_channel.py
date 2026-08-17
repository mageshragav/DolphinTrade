"""Order channel: a persistent websocket for order placement and deal
tracking (separate from the candle-fetch socket).

- place(): sends e:23 (binary) or e:1032 (multiplier) and waits for the
  matching response (by uuid) to return the deal object.
- deals(): latest deal states seen on the wire (e:22 push updates), used
  by the tracker to settle trades from the broker's own data.
- Reconnects automatically if the socket dies.
"""

import json
import logging
import queue
import threading
import time

from websocket import create_connection

from common.constants import HEADERS, OLYMP_WS, OLYMP_ORIGIN, OLYMP_EXTENSIONS
from common.socketkey.olymptradekey import OlympTradeConnection

LOGGER = logging.getLogger('dolphin')


class OrderChannel:
    def __init__(self, group='demo'):
        self.key = OlympTradeConnection(group=group)   # wallet + account_id
        self.group = group
        self.ws = None
        self._queue = queue.Queue()
        self._lock = threading.Lock()
        self.running = False
        self._thread = None
        self.deals = {}                                # deal_id -> latest deal dict
        self.connect()

    # -- connection ---------------------------------------------------------

    def connect(self):
        try:
            self.ws = create_connection(OLYMP_WS, header=HEADERS, origin=OLYMP_ORIGIN,
                                        extensions=OLYMP_EXTENSIONS, timeout=30)
            self.running = True
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._reader, daemon=True)
                self._thread.start()
            LOGGER.info('order channel connected')
        except Exception as e:
            LOGGER.warning(f'order channel connect failed: {e}')
            self.running = False
            self.ws = None

    def _reader(self):
        while self.running:
            try:
                raw = self.ws.recv()
                if raw:
                    self._queue.put(raw)
                    self._track(raw)
            except Exception as e:
                LOGGER.warning(f'order channel socket error ({e}) - reconnecting')
                self.running = False
                time.sleep(5)
                self.connect()
                return

    def _track(self, raw):
        try:
            msgs = json.loads(raw) if isinstance(raw, str) else raw
            for m in (msgs if isinstance(msgs, list) else [msgs]):
                d = m.get('d')
                if not isinstance(d, list) or not d or not isinstance(d[0], dict):
                    continue
                deal = d[0]
                if deal.get('id'):
                    self.deals[str(deal['id'])] = deal
        except Exception:
            pass

    # -- placement ----------------------------------------------------------

    def place(self, order_type: str, direction: str, pair: str, amount,
              duration_sec=None, multiplicator=100, stop_loss=None,
              take_profit=None, timeout=12) -> dict:
        """Place an order and return the broker deal dict ({} if no reply)."""
        if self.ws is None:
            self.connect()
        if order_type == 'binary':
            key = self.key.get_bet_key(direction, pair, str(amount),
                                       str(duration_sec or 60))
        else:
            key = self.key.get_order_key(direction, pair, str(amount),
                                         multiplicator, stop_loss, take_profit)
        payload = json.dumps(key)
        uuid = key[0]['uuid']
        with self._lock:
            self.ws.send(payload)

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                msgs = json.loads(raw) if isinstance(raw, str) else raw
                for m in (msgs if isinstance(msgs, list) else [msgs]):
                    if m.get('uuid') != uuid:
                        continue
                    err = m.get('err') or []
                    if err:
                        return {'error': err[0].get('mess', 'broker error'),
                                'code': err[0].get('code', '')}
                    if isinstance(m.get('d'), list) and m['d']:
                        deal = m['d'][0] if isinstance(m['d'][0], dict) else {}
                        if deal.get('id'):
                            self.deals[str(deal['id'])] = deal
                        return deal
                    return {}                      # matched but empty reply
            except Exception:
                continue
        LOGGER.warning(f'order placement timed out waiting for uuid {uuid}')
        return {}

    # -- helpers ------------------------------------------------------------

    def deal_states(self):
        """Snapshot of the latest known deal states (for settlement)."""
        return list(self.deals.values())

    def live_deals_key(self):
        return self.key.get_on_live_bets()

    def disconnect(self):
        self.running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
