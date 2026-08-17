"""Olymp Trade connector: candles, bet placement, verification, session.

Reuses the existing websocket client (dolphin/common/socketconnect).
Session token comes from the settings/DB; it expires periodically and is
refreshed via the Settings UI (v1) - Playwright auto-login is a v2 path.
"""

import base64
import json
import logging
from datetime import datetime, timezone

import pandas as pd

from app.config import get_settings

LOGGER = logging.getLogger('dolphin')


def token_expiry() -> datetime | None:
    """Decode the access_token JWT and return its exp (or None if unparsable)."""
    try:
        from common.constants import cookies
        tok = cookies.get('access_token', '')
        if not tok:
            return None
        payload = json.loads(base64.urlsafe_b64decode(tok.split('.')[1] + '=='))
        return datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
    except Exception:
        return None


def token_ok() -> bool:
    exp = token_expiry()
    return exp is not None and exp > datetime.now(timezone.utc)


class OlympConnector:
    def __init__(self, access_token: str = None, group: str = None, pair_suffix: str = ''):
        from common.constants import cookies, cookies_str

        settings = get_settings()
        self.group = group or settings.olymp_group
        self.pair_suffix = pair_suffix or settings.olymp_pair_suffix
        if access_token:
            cookies['access_token'] = access_token
            import common.constants as const
            const.cookies_str = '; '.join(f'{k}={v}' for k, v in cookies.items())
            const.HEADERS = {'Cookie': const.cookies_str,
                             'User-Agent': const.HEADERS.get('User-Agent', 'Mozilla/5.0')}
        self.client = None
        self.channel = None
        self._connected = False
        self._make_client()

    def set_token(self, access_token: str) -> bool:
        """Hot-swap the session token and reconnect both sockets.

        Returns True when the new token authenticates (wallet fetch succeeds).
        """
        from common import constants as const
        const.set_access_token(access_token)
        for obj in (self.client, self.channel):
            try:
                if obj is not None:
                    obj.disconnect()
            except Exception:
                pass
        self.client = None
        self.channel = None
        self._connected = False
        self._make_client()
        ok = self.client is not None
        if ok and token_ok():
            exp = token_expiry()
            LOGGER.info(f'session token hot-swapped, valid until '
                        f'{exp:%Y-%m-%d %H:%M} UTC')
        return ok

    def _make_channel(self):
        from app.connectors.order_channel import OrderChannel
        try:
            self.channel = OrderChannel(group=self.group)
            return self.channel
        except Exception as e:
            LOGGER.warning(f'order channel create failed: {e}')
            self.channel = None
            return None

    # -- market data -------------------------------------------------------

    def _ensure_client(self):
        """Recreate the websocket client if it is dead or missing."""
        if self.client is None:
            self._make_client()
        return self.client

    def _make_client(self):
        from common.socketconnect.Olymptradeconnect import OlympTradeClient
        try:
            self.client = OlympTradeClient(group=self.group)
            self._connected = True
        except Exception as e:
            LOGGER.warning(f'olymp connect failed: {e}')
            self.client = None
            self._connected = False
        return self.client

    def fetch_candles(self, pairs, size=600) -> pd.DataFrame:
        for attempt in (1, 2):
            client = self._ensure_client()
            if client is None:
                return pd.DataFrame()
            try:
                frames = []
                for p in pairs:
                    data = client.get_candle(size=size, pair=p)
                    if not data:
                        continue
                    candles = data[0].get('candles') if isinstance(data, list) else data.get('candles')
                    if not candles:
                        continue
                    df = pd.DataFrame(candles)
                    df['symbol'] = 'FX:' + p   # same convention as trades/DB
                    frames.append(df)
                return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            except Exception as e:
                LOGGER.warning(f'fetch_candles attempt {attempt} failed: {e}')
                self._connected = False
                self.client = None   # force a fresh connection next attempt
        return pd.DataFrame()

    # -- execution ----------------------------------------------------------

    def place_bet(self, symbol, direction, amount, duration_sec=None,
                  order_type='binary', multiplicator=100,
                  take_profit=None, stop_loss=None) -> dict:
        """Place an order and return the broker deal dict.

        order_type: 'binary' (e:23, needs duration_sec) | 'multiplier' (e:1032).
        take_profit/stop_loss: {'type': 'price', 'value': <level>, 'trailing': False}
        or None. Pair names are sent on the normal market (EURUSD); the OTC
        suffix is only appended when olymp_pair_suffix is set.
        """
        pair = symbol.split(':')[-1] + self.pair_suffix
        for attempt in (1, 2):
            if self.channel is None:
                self._make_channel()
            if self.channel is None:
                raise RuntimeError('order channel not connected')
            try:
                deal = self.channel.place(order_type, direction, pair, amount,
                                          duration_sec=duration_sec,
                                          multiplicator=multiplicator,
                                          stop_loss=stop_loss,
                                          take_profit=take_profit)
                if not deal:
                    raise RuntimeError('broker returned no deal (empty response)')
                return deal
            except Exception as e:
                LOGGER.warning(f'place_bet attempt {attempt} failed: {e}')
                try:
                    self.channel.disconnect()
                except Exception:
                    pass
                self.channel = None
        raise RuntimeError('bet failed after reconnect attempts')

    def verify_live_bets(self):
        """Best-effort verification channel (olymp WS live bets)."""
        try:
            return self.client.get_onlive_bet()
        except Exception as e:
            LOGGER.warning(f'live-bet verification failed: {e}')
            return None

    def disconnect(self):
        if self.channel:
            try:
                self.channel.disconnect()
            except Exception:
                pass
            self.channel = None
        try:
            self.client.disconnect()
        except Exception:
            pass
