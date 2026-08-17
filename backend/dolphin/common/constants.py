import os
from datetime import *
import pytz
cur_dir = os.getcwd()

import os as _os


def _load_env_file():
    """Populate os.environ from backend/.env (repo-relative, gitignored).

    Secrets (olymp tokens, telegram credentials) live ONLY here, never in
    the committed source. Without the file the session is empty and the
    platform refuses to trade (see token_ok / startup checks).
    """
    path = _os.path.join(_os.path.dirname(_os.path.dirname(
        _os.path.dirname(_os.path.abspath(__file__)))), '.env')
    if not _os.path.exists(path):
        return
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, _, v = line.partition('=')
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in _os.environ:
                    _os.environ[k] = v
    except Exception:
        pass


_load_env_file()


def _env(key: str, default: str = '') -> str:
    return _os.environ.get(key, default)


#########OLYMPTRADE CONSTANTS####################
# HEADERS = {
#     'Pragma': 'no-cache',
#     'Origin': 'https://olymptrade.com',
#     'Accept-Language': 'en-US,en;q=0.9',
#     'Sec-WebSocket-Key': 'PPg0ZN4Q6pVf8r5eKSucFw==',
#     'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
#     'Upgrade': 'websocket',
#     'Cache-Control': 'no-cache',
#     'Connection': 'Upgrade',
#     'Sec-WebSocket-Version': '13',
#     'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits',
# }
cookies = {
    'checked': '1',
    'guest_id': '2646ae13-0010-861c-36f4-998978608a4f',
    'enterdate': '2026-08-16+10%3A56%3A59',
    'lang': 'en_US',
    '__cflb': '02DiuGSURUTCLDAS4xX8HLyoQLMaecKhHs1WqLS7f4Uyr',
    'uhdwidv2': 'hi_KTF0xnyjUuzZpaWSeWAgF7CdqZsYoUG-',
    'ecp': 'hi_KTF0xnyjUuzZpaWSeWAgF7CdqZsYoUG-',
    'ece': 'hi_KTF0xnyjUuzZpaWSeWAgF7CdqZsYoUG-',
    'ecc': 'hi_KTF0xnyjUuzZpaWSeWAgF7CdqZsYoUG-',
    'otrhIIBzICu': 'a4c45c4101c87a0458b32ff9245cd0ef',
    '_cfuvid': 'DXYIfSfGGKd8j2OJueeVn18M0a6CgxevYYFSGPSjVSA-1786867019.2185855-1.0.1.1-dnUlvRPylr0r78t1biEOGzHzidSlwM1b_CUq04bUHfE',
    'access_token': _env('DT_OLYMP_ACCESS_TOKEN'),
    'refresh_token': _env('DT_OLYMP_REFRESH_TOKEN'),
}
  
cookies_str = '; '.join([f'{key}={value}' for key, value in cookies.items()])


def set_cookie(name: str, value: str) -> None:
    """Update a session cookie in place and refresh the derived strings."""
    cookies[name] = value
    globals()['cookies_str'] = '; '.join(f'{k}={v}' for k, v in cookies.items())
    if 'HEADERS' in globals():
        globals()['HEADERS']['Cookie'] = globals()['cookies_str']
    if 'DEALS_HEADERS' in globals():
        globals()['DEALS_HEADERS']['cookie'] = globals()['cookies_str']


def set_access_token(token: str) -> None:
    """Hot-swap the session token in place (no restart needed)."""
    set_cookie('access_token', token)
# HEADERS = {
#     'Pragma': 'no-cache',
#     'Origin': 'https://olymptrade.com',
#     'Accept-Language': 'en-US,en;q=0.9',
#     'Sec-WebSocket-Key': 'ZAcZTkGmbyl6QTA/qoXEng==',
#     'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
#     'Upgrade': 'websocket',
#     'Cookie': cookies_str,
#     'Cache-Control': 'no-cache',
#     'Connection': 'Upgrade',
#     'Sec-WebSocket-Version': '13',    
# }
# cookies_str = '<from .env - see _load_env_file>'
# NOTE: no 'Origin' here on purpose - websocket-client auto-appends its own
# 'Origin: https://<ws-host>' line, which the broker rejects (invalid_origin).
# Callers pass origin='https://olymptrade.com' to create_connection instead.
# Sec-WebSocket-Extensions is also omitted: it must be negotiated through the
# lib's extensions= option so compressed frames are decompressed.
HEADERS = {
    'Cookie': cookies_str,
    'Sec-GPC': '1',
    'Cache-Control': 'no-cache',
    'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
    'Pragma': 'no-cache',
    'Connection': 'Upgrade',
    'Sec-WebSocket-Version': '13',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36',
}
OLYMP_ORIGIN = 'https://olymptrade.com'
OLYMP_EXTENSIONS = ['permessage-deflate; client_max_window_bits']
DEALS_HEADERS = {
    'authority': 'gw.olymptrade.com',
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'cache-control': 'max-age=0',
    'content-type': 'application/json',
    'cookie': cookies_str,
    'origin': 'https://olymptrade.com',
    'referer': 'https://olymptrade.com/',
    'sec-ch-ua': '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'x-cid-app': 'web@OlympTrade@2023.4.20803@20803',
    'x-cid-device': '@@desktop',
    'x-cid-os': 'linux@x86_64',
    'x-cid-ver': '1',
}
OLYMP_WS = r"wss://ws.olymptrade.com/otp?cid_ver=1&cid_app=web%40OlympTrade%402026.3.2330613%402330613&cid_device=%40%40desktop&cid_os=linux%40none"
TRADINGVIEW_URL = 'https://scanner.tradingview.com/symbol?symbol=FX_IDC:{symbol}&fields=Recommend.Other|{duration},Recommend.All|{duration},Recommend.MA|{duration},RSI|{duration},RSI[1]|{duration},Stoch.K|{duration},Stoch.D|{duration},Stoch.K[1]|{duration},Stoch.D[1]|{duration},CCI20|{duration},CCI20[1]|{duration},ADX|{duration},ADX+DI|{duration},ADX-DI|{duration},ADX+DI[1]|{duration},ADX-DI[1]|{duration},AO|{duration},AO[1]|{duration},AO[2]|{duration},Mom|{duration},Mom[1]|{duration},MACD.macd|{duration},MACD.signal|{duration},Rec.Stoch.RSI|{duration},Stoch.RSI.K|{duration},Rec.WR|{duration},W.R|{duration},Rec.BBPower|{duration},BBPower|{duration},Rec.UO|{duration},UO|{duration},EMA10|{duration},close|{duration},SMA10|{duration},EMA20|{duration},SMA20|{duration},EMA30|{duration},SMA30|{duration},EMA50|{duration},SMA50|{duration},EMA100|{duration},SMA100|{duration},EMA200|{duration},SMA200|{duration},Rec.Ichimoku|{duration},Ichimoku.BLine|{duration},Rec.VWMA|{duration},VWMA|{duration},Rec.HullMA9|{duration},HullMA9|{duration},Pivot.M.Classic.S3|{duration},Pivot.M.Classic.S2|{duration},Pivot.M.Classic.S1|{duration},Pivot.M.Classic.Middle|{duration},Pivot.M.Classic.R1|{duration},Pivot.M.Classic.R2|{duration},Pivot.M.Classic.R3|{duration},Pivot.M.Fibonacci.S3|{duration},Pivot.M.Fibonacci.S2|{duration},Pivot.M.Fibonacci.S1|{duration},Pivot.M.Fibonacci.Middle|{duration},Pivot.M.Fibonacci.R1|{duration},Pivot.M.Fibonacci.R2|{duration},Pivot.M.Fibonacci.R3|{duration},Pivot.M.Camarilla.S3|{duration},Pivot.M.Camarilla.S2|{duration},Pivot.M.Camarilla.S1|{duration},Pivot.M.Camarilla.Middle|{duration},Pivot.M.Camarilla.R1|{duration},Pivot.M.Camarilla.R2|{duration},Pivot.M.Camarilla.R3|{duration},Pivot.M.Woodie.S3|{duration},Pivot.M.Woodie.S2|{duration},Pivot.M.Woodie.S1|{duration},Pivot.M.Woodie.Middle|{duration},Pivot.M.Woodie.R1|{duration},Pivot.M.Woodie.R2|{duration},Pivot.M.Woodie.R3|{duration},Pivot.M.Demark.S1|{duration},Pivot.M.Demark.Middle|{duration},Pivot.M.Demark.R1|{duration}&no_404=true'
#############TRADING VIEW CONSTANTS################
EXCHANGE = 'FX_IDC'
SCREENER = 'forex'
EUR_SYMBOLS = ['EURUSD','EURJPY', 'GBPUSD'] #'EURAUD' #,'EURJPY' #'EURGBP'
GBP_SYMBOLS = ['GBPUSD'] #,'GBPJPY'
CAD_SYMBOLS = ['CADJPY','CADCHF'] #'CADCHF'
AUD_SYMBOLS = ['AUDJPY','AUDUSD'] #,'AUDCHF','AUDNZD',
USD_SYMBOLS = ['USDCAD','USDJPY'] #'USDCHF'
# COMMON_SYMBOLS = GBP_SYMBOLS+EUR_SYMBOLS+CAD_SYMBOLS+AUD_SYMBOLS+USD_SYMBOLS
# COMMON_SYMBOLS = ['EURUSD','GBPUSD','AUDUSD','USDCAD','USDJPY','EURJPY','USDCAD'] #'EURGBP','GBPAUD','GBPCAD',
COMMON_SYMBOLS = ['EURUSD']
ALL_SYMBOLS = GBP_SYMBOLS+EUR_SYMBOLS+AUD_SYMBOLS
TRADE_SYMBOLS = ['AUDUSD','EURJPY']
#,'USDJPY','GBPUSD','USDCHF','EURJPY','USDCAD','AUDUSD', 'EURGBP','EURJPY'
##############based on indian timings#################
#FROM 5.30AM TO 2.30PM
current_date_time = datetime.now(pytz.timezone('UTC')).astimezone(pytz.timezone('Asia/Kolkata'))
TIME_5_30 = datetime.now().replace(hour=0,minute=0)
TIME_14_30 = datetime.now().replace(hour=23,minute=30)
# SYMBOLS_LIST_5_TO_2 = ['AUDNZD','AUDJPY','AUDUSD','USDJPY','GBPUSD','USDCHF']
SYMBOLS_LIST_5_TO_2 = COMMON_SYMBOLS
#FROM 12.30PM TO 8.30PM
TIME_12_00 = datetime.now().replace(hour=12,minute=30)
TIME_8_30 = datetime.now().replace(hour=20,minute=30)
SYMBOLS_LIST_12_TO_8 = COMMON_SYMBOLS
#FROM 5.30PM TO 2.30AM
TIME_17_30 = datetime.now().replace(hour=17,minute=30)
TIME_2_30 = datetime.now().replace(hour=2,minute=30)+timedelta(days=1)
SYMBOLS_LIST_17_TO_2 = COMMON_SYMBOLS

TIME_SYMBOL_MAPPING = {
    (TIME_5_30, TIME_14_30): SYMBOLS_LIST_5_TO_2,
    # (TIME_12_00, TIME_8_30): SYMBOLS_LIST_12_TO_8,
    # (TIME_17_30, TIME_2_30): SYMBOLS_LIST_17_TO_2,
}
#####################TELEGRAM BOT CONSTANTS########################333

IMAGE_GREEN= '/images/green.jpg'
IMAGE_RED = '/images/red.jpg'

#telegram client
BOT_TOKEN = _env('DT_TELEGRAM_BOT_TOKEN')
CHAT_ID = _env('DT_TELEGRAM_CHAT_ID')
GROUP_ID = _env('DT_TELEGRAM_GROUP_ID')
##############################################################################