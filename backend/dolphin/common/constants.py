import os
from datetime import *
import pytz
cur_dir = os.getcwd()
#########OLYMPTRADE CONSTANTS####################
# HEADERS = {
#     'Pragma': 'no-cache',
#     'Origin': 'https://olymptrade.com',
#     'Accept-Language': 'en-US,en;q=0.9',
#     'Sec-WebSocket-Key': 'PPg0ZN4Q6pVf8r5eKSucFw==',
#     'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
#     'Upgrade': 'websocket',
#     'Cache-Control': 'no-cache',
#     'Cookie': 'guest_id=1000163614828235836441830584547061689779910043140201155559642052; __hstc=95761603.f2de272f989c05048cc39d36a27455e2.1689779911863.1689779911863.1689779911863.1; hubspotutk=f2de272f989c05048cc39d36a27455e2; _gcl_au=1.1.390423421.1689779917; _rdt_uuid=1689779917470.1538a053-37df-4cae-9c20-4d68eb5b1010; _scid=4b9fb4ab-6e0d-4d9c-97b5-d1675ed84588; _tt_enable_cookie=1; _ttp=VsIt3QMJYaEUvKVyIfbT2Jr9IHo; __exponea_etc__=2ce15ac4-a131-4833-8717-e584109f6a99; _sctr=1%7C1689739200000; _scid_r=4b9fb4ab-6e0d-4d9c-97b5-d1675ed84588; _ga=GA1.2.1373637290.1689779917; _ga_SN8XZNJ2M7=GS1.1.1689779917.1.1.1689780108.60.0.0; enterdate=2023-08-17+15%3A54%3A24; lang=en_US; tr_http_referer=af_siteid%3DLPL45-04en%26click_id%3D8f89e3b2-fe99-485f-a134-36f8abf4cee2%26noapp%3D%26ref%3Dcpa_kf_1947474%26traffic%3D1%26utm_campaign%3D25%26utm_content%3D2NKZ%26utm_medium%3Dcpa%26utm_source%3D1947474%26utm_term%3D1947474; tr_request_uri=%2Fl%2FLPL45-04en%2Fcpa_kf_1947474%3Faf_siteid%3DLPL45-04en%26click_id%3D8f89e3b2-fe99-485f-a134-36f8abf4cee2%26http_referer%3Daf_siteid%25253DLPL45-04en%252526click_id%25253D8f89e3b2-fe99-485f-a134-36f8abf4cee2%252526noapp%25253D%252526ref%25253Dcpa_kf_1947474%252526traffic%25253D1%252526utm_campaign%25253D25%252526utm_content%25253D2NKZ%252526utm_medium%25253Dcpa%252526utm_source%25253D1947474%252526utm_term%25253D1947474%26noapp%3D%26ref%3Dcpa_kf_1947474%26traffic%3D1%26utm_campaign%3D25%26utm_content%3D2NKZ%26utm_medium%3Dcpa%26utm_source%3D1947474%26utm_term%3D1947474%26pixel%3D1; tr_traffic=%7B%22created_at%22%3A%222023-09-07+16%3A52%3A26%22%2C%22ref%22%3A%22cpa_kf_1947474%22%2C%22ref_channel%22%3A%22cpa%22%2C%22land%22%3A%22LPL45-04en%22%2C%22utm_campaign%22%3A%2225%22%2C%22utm_term%22%3A%221947474%22%2C%22utm_content%22%3A%222NKZ%22%2C%22utm_medium%22%3A%22cpa%22%2C%22utm_source%22%3A%221947474%22%2C%22guest_id%22%3A%221000163614828235836441830584547061689779910043140201155559642052%22%7D; amp_fffbd0_olymptrade.com=JWltmevrgCidRd9-DHdw7q.MTgzZjFmNzEtMTUyNy00YTAyLTkyZDQtYWY5YzY3Mzg0Nzhj..1h9o12j2e.1h9o12j2e.5.1.6; checked=1; __cflb=02DiuEiGfEtZNVDV1unvre1VCYy669HRvd3AjJcgk7exU; amp_fffbd0=JWltmevrgCidRd9-DHdw7q.MTgzZjFmNzEtMTUyNy00YTAyLTkyZDQtYWY5YzY3Mzg0Nzhj..1h9r60j9m.1h9r60j9m.0.17.17; __cf_bm=6b2c3A2mrYquotBncpcEQnYNvY7Oca2uYsLHZ449noI-1694203138-0-ARaDMM1LmBseniChIh5JKyDlAfi8ejQhcQ1L9PjJ2L0sfEisEj4M//uuEHdVpbqZ8D8/FRN3Byrvea1I7fsQGYM=; _cfuvid=9mQv1_EFb_I4_UJhV18zQUkTD7zE1rOYpCN6_NrBS1c-1694203138424-0-604800000; jwt_auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE2OTQyMDMxMzgsIm5iZiI6MTY5NDIwMzEzOCwiZXhwIjoxNjk0Mjg5NTM4LCJ1c2VyX2lkIjo0NjMwMDA4NCwiZW1haWwiOiJtYWdlc2htZ3IxQGdtYWlsLmNvbSJ9.c-xldHLYoVB1RTMiSWiOHWImVVQllK-xv6Gk_enEe49S-HO5ugtb59V4XjFfe6lpczPWrFtXUHOCXfcRvbYs8yqMC2URLayH8JjCGcDInrWmIXOPzCJbTsvoAJaT5g6pYnz1sM8aMr2RAXRMhGDrh7GZXCPEfkHngc6QK7od5IdPYmgvySuRBDyNtnXilY-hWJ84g8SiJRZ-0aZFG3mg_yvyunkuZFhawSPzqMP2LC6azJS5J4cMyBy1yY9FICR_05JWkiSe9zqODQul29riayF_avFG30Iov7Hdm_2CTXoWTObcUJExIa-CNNHXp9Wn1-HuVQxDRCk2ZcWXA5ogHeK3PWcofz6cherMTE9kO1-45kUpiPXKyqXfiocyVfglubHWCEN26pjg7_0va110XItmoejvWd-Cl1Iqq-qWC91Gr6659g0xX0kTA2AeerjkgtFTuhbaiWUVj9yiJG7RH4XtN9zDZwIv4Ba2Z3mybW9s4tDxamLXuQ8OcbMmzfMZI4w26764NZH75FtJxE5QcIps5BMs29P0BFyStR07-KnfT9VKew1Vej3PUFR_-aPcDMOsg_T-OO0VtJ25qltjL0fqrLXzSQBVYImL7acQwpKkubzFpF0Qlo_Cm9-N4IWM_kV9gVUMZ2xWmbrUg7UZe_LOWCjdpf238BRqTSHc_3U; access_token=PLACEHOLDER_JWT',
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
    'access_token': 'PLACEHOLDER_JWT',
    'refresh_token': 'PLACEHOLDER_JWT',
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
# cookies_str = "'Cookie': 'guest_id=1000163614828235836441830584547061689779910043140201155559642052; __hstc=95761603.f2de272f989c05048cc39d36a27455e2.1689779911863.1689779911863.1689779911863.1; hubspotutk=f2de272f989c05048cc39d36a27455e2; _gcl_au=1.1.390423421.1689779917; _rdt_uuid=1689779917470.1538a053-37df-4cae-9c20-4d68eb5b1010; _scid=4b9fb4ab-6e0d-4d9c-97b5-d1675ed84588; _tt_enable_cookie=1; _ttp=VsIt3QMJYaEUvKVyIfbT2Jr9IHo; __exponea_etc__=2ce15ac4-a131-4833-8717-e584109f6a99; _sctr=1%7C1689739200000; _scid_r=4b9fb4ab-6e0d-4d9c-97b5-d1675ed84588; _ga=GA1.2.1373637290.1689779917; _ga_SN8XZNJ2M7=GS1.1.1689779917.1.1.1689780108.60.0.0; enterdate=2023-09-14+21%3A00%3A35; lang=en_US; checked=1; __cflb=0H28v9SCd6TDXBB3Aqm3oESsmV2UcyTkz4oMPYYhJjE; amp_fffbd0_olymptrade.com=JWltmevrgCidRd9-DHdw7q.MTgzZjFmNzEtMTUyNy00YTAyLTkyZDQtYWY5YzY3Mzg0Nzhj..1hbg1tuuj.1hbg1tuuj.5.1.6; tr_http_referer=af_siteid%3DLPL45-04en%26click_id%3Ddddc2e7e-16f6-4846-ad65-d7fc4633054a%26noapp%3D%26ref%3Dcpa_kf_1947474%26traffic%3D1%26utm_campaign%3D25%26utm_content%3D2NKZ%26utm_medium%3Dcpa%26utm_source%3D1947474%26utm_term%3D1947474; tr_request_uri=%2Fl%2FLPL45-04en%2Fcpa_kf_1947474%3Faf_siteid%3DLPL45-04en%26click_id%3Ddddc2e7e-16f6-4846-ad65-d7fc4633054a%26http_referer%3Daf_siteid%25253DLPL45-04en%252526click_id%25253Ddddc2e7e-16f6-4846-ad65-d7fc4633054a%252526noapp%25253D%252526ref%25253Dcpa_kf_1947474%252526traffic%25253D1%252526utm_campaign%25253D25%252526utm_content%25253D2NKZ%252526utm_medium%25253Dcpa%252526utm_source%25253D1947474%252526utm_term%25253D1947474%26noapp%3D%26ref%3Dcpa_kf_1947474%26traffic%3D1%26utm_campaign%3D25%26utm_content%3D2NKZ%26utm_medium%3Dcpa%26utm_source%3D1947474%26utm_term%3D1947474%26pixel%3D1; tr_traffic=%7B%22created_at%22%3A%222023-09-29+11%3A47%3A24%22%2C%22ref%22%3A%22cpa_kf_1947474%22%2C%22ref_channel%22%3A%22cpa%22%2C%22land%22%3A%22LPL45-04en%22%2C%22utm_campaign%22%3A%2225%22%2C%22utm_term%22%3A%221947474%22%2C%22utm_content%22%3A%222NKZ%22%2C%22utm_medium%22%3A%22cpa%22%2C%22utm_source%22%3A%221947474%22%2C%22guest_id%22%3A%221000163614828235836441830584547061689779910043140201155559642052%22%7D; __cf_bm=d5yeGkAWIjG6vhBEAYbFdvaKW14Pz7M5E9u3rz5rfiI-1695977504-0-AVPoywl/BLxJbMXe4r893jbArZT4VqOJqIdAcIvrYuEIg/u/y/lSK4ioJHbU8xUKLPCQoxh6gViTI4bLqoSM28c=; _cfuvid=ujHq7vvqfi9tw.eZNfNfCsSNvvEtwClQDkPJDq3Vp50-1695977504961-0-604800000; amp_fffbd0=JWltmevrgCidRd9-DHdw7q.MTgzZjFmNzEtMTUyNy00YTAyLTkyZDQtYWY5YzY3Mzg0Nzhj..1hbg1tsda.1hbg266a0.0.27.27; jwt_auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE2OTU5Nzc1MTIsIm5iZiI6MTY5NTk3NzUxMiwiZXhwIjoxNjk2MDYzOTEyLCJ1c2VyX2lkIjo0NjMwMDA4NCwiZW1haWwiOiJtYWdlc2htZ3IxQGdtYWlsLmNvbSJ9.g0HtaxdHy8e7qzjaMBaGWRE8U_LEvXtQpX1lX1CjxZJ9o40quUSUJzX6NlpLH7MtI_ItRPFXxK3Fa-B3kgcwKpLAlGbjb8BSslmBxfYUV1LvLtSvrs0tIKPoLIvaBn5LJ3Ytz7V7eEeBeeYcFtzAk-OWZwdiC-C01SAHnyQ0nNYNl4JiFVgd4QiTyJkHHkN535DsAphdlDeEqAVwmvoqqG5sNzv774JxpJhkGIXvtf8Ndv8_F8yflTOfoyWmo0x356qMl7d2SjcwfGpHwQJA2toyadmvf2Mvqh-kmmUl1YAydoLxrfoSnjojTJwpORiY4pgPNA8IVW6oUAzyZaZ9KGXSdi6G61UjrafDjKVgSs00cbVT7rtrOVLRLavdkHXJaWAgU1N4JD0xPl2FY93_EOXyqCddTPJpA53Bj7gHgGYm2JKJFgwOV6RhnGchAHUj5wiOvweairoRE_dE1sqqY6xtBbK-rTtMTm2cszP7ePf3UVbtUPpD24kyK_yiT_t6vGPL6Wld_M1KbuohmgDIioUE5ruJ_pYI70RKcTZD-n5u5Pb52xcULtvk41RW4GN_UEKFt2UgQ_yLC1PGFmmcYdPwJa_G9SByzCRKPT1Oq1BfjdpcuHuzc9ceeJP30Hvwsw7zShpuXWhNv6Fojn8P4hswUazGjGo40-nMUzRC8rU; access_token=PLACEHOLDER_JWT'"
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
BOT_TOKEN = 'PLACEHOLDER_BOT_TOKEN'
CHAT_ID = '883318761'
GROUP_ID = '-1001858529704'
##############################################################################