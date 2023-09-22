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
#     'Cookie': 'guest_id=1000163614828235836441830584547061689779910043140201155559642052; __hstc=95761603.f2de272f989c05048cc39d36a27455e2.1689779911863.1689779911863.1689779911863.1; hubspotutk=f2de272f989c05048cc39d36a27455e2; _gcl_au=1.1.390423421.1689779917; _rdt_uuid=1689779917470.1538a053-37df-4cae-9c20-4d68eb5b1010; _scid=4b9fb4ab-6e0d-4d9c-97b5-d1675ed84588; _tt_enable_cookie=1; _ttp=VsIt3QMJYaEUvKVyIfbT2Jr9IHo; __exponea_etc__=2ce15ac4-a131-4833-8717-e584109f6a99; _sctr=1%7C1689739200000; _scid_r=4b9fb4ab-6e0d-4d9c-97b5-d1675ed84588; _ga=GA1.2.1373637290.1689779917; _ga_SN8XZNJ2M7=GS1.1.1689779917.1.1.1689780108.60.0.0; enterdate=2023-08-17+15%3A54%3A24; lang=en_US; tr_http_referer=af_siteid%3DLPL45-04en%26click_id%3D8f89e3b2-fe99-485f-a134-36f8abf4cee2%26noapp%3D%26ref%3Dcpa_kf_1947474%26traffic%3D1%26utm_campaign%3D25%26utm_content%3D2NKZ%26utm_medium%3Dcpa%26utm_source%3D1947474%26utm_term%3D1947474; tr_request_uri=%2Fl%2FLPL45-04en%2Fcpa_kf_1947474%3Faf_siteid%3DLPL45-04en%26click_id%3D8f89e3b2-fe99-485f-a134-36f8abf4cee2%26http_referer%3Daf_siteid%25253DLPL45-04en%252526click_id%25253D8f89e3b2-fe99-485f-a134-36f8abf4cee2%252526noapp%25253D%252526ref%25253Dcpa_kf_1947474%252526traffic%25253D1%252526utm_campaign%25253D25%252526utm_content%25253D2NKZ%252526utm_medium%25253Dcpa%252526utm_source%25253D1947474%252526utm_term%25253D1947474%26noapp%3D%26ref%3Dcpa_kf_1947474%26traffic%3D1%26utm_campaign%3D25%26utm_content%3D2NKZ%26utm_medium%3Dcpa%26utm_source%3D1947474%26utm_term%3D1947474%26pixel%3D1; tr_traffic=%7B%22created_at%22%3A%222023-09-07+16%3A52%3A26%22%2C%22ref%22%3A%22cpa_kf_1947474%22%2C%22ref_channel%22%3A%22cpa%22%2C%22land%22%3A%22LPL45-04en%22%2C%22utm_campaign%22%3A%2225%22%2C%22utm_term%22%3A%221947474%22%2C%22utm_content%22%3A%222NKZ%22%2C%22utm_medium%22%3A%22cpa%22%2C%22utm_source%22%3A%221947474%22%2C%22guest_id%22%3A%221000163614828235836441830584547061689779910043140201155559642052%22%7D; amp_fffbd0_olymptrade.com=JWltmevrgCidRd9-DHdw7q.MTgzZjFmNzEtMTUyNy00YTAyLTkyZDQtYWY5YzY3Mzg0Nzhj..1h9o12j2e.1h9o12j2e.5.1.6; checked=1; __cflb=02DiuEiGfEtZNVDV1unvre1VCYy669HRvd3AjJcgk7exU; amp_fffbd0=JWltmevrgCidRd9-DHdw7q.MTgzZjFmNzEtMTUyNy00YTAyLTkyZDQtYWY5YzY3Mzg0Nzhj..1h9r60j9m.1h9r60j9m.0.17.17; __cf_bm=6b2c3A2mrYquotBncpcEQnYNvY7Oca2uYsLHZ449noI-1694203138-0-ARaDMM1LmBseniChIh5JKyDlAfi8ejQhcQ1L9PjJ2L0sfEisEj4M//uuEHdVpbqZ8D8/FRN3Byrvea1I7fsQGYM=; _cfuvid=9mQv1_EFb_I4_UJhV18zQUkTD7zE1rOYpCN6_NrBS1c-1694203138424-0-604800000; jwt_auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE2OTQyMDMxMzgsIm5iZiI6MTY5NDIwMzEzOCwiZXhwIjoxNjk0Mjg5NTM4LCJ1c2VyX2lkIjo0NjMwMDA4NCwiZW1haWwiOiJtYWdlc2htZ3IxQGdtYWlsLmNvbSJ9.c-xldHLYoVB1RTMiSWiOHWImVVQllK-xv6Gk_enEe49S-HO5ugtb59V4XjFfe6lpczPWrFtXUHOCXfcRvbYs8yqMC2URLayH8JjCGcDInrWmIXOPzCJbTsvoAJaT5g6pYnz1sM8aMr2RAXRMhGDrh7GZXCPEfkHngc6QK7od5IdPYmgvySuRBDyNtnXilY-hWJ84g8SiJRZ-0aZFG3mg_yvyunkuZFhawSPzqMP2LC6azJS5J4cMyBy1yY9FICR_05JWkiSe9zqODQul29riayF_avFG30Iov7Hdm_2CTXoWTObcUJExIa-CNNHXp9Wn1-HuVQxDRCk2ZcWXA5ogHeK3PWcofz6cherMTE9kO1-45kUpiPXKyqXfiocyVfglubHWCEN26pjg7_0va110XItmoejvWd-Cl1Iqq-qWC91Gr6659g0xX0kTA2AeerjkgtFTuhbaiWUVj9yiJG7RH4XtN9zDZwIv4Ba2Z3mybW9s4tDxamLXuQ8OcbMmzfMZI4w26764NZH75FtJxE5QcIps5BMs29P0BFyStR07-KnfT9VKew1Vej3PUFR_-aPcDMOsg_T-OO0VtJ25qltjL0fqrLXzSQBVYImL7acQwpKkubzFpF0Qlo_Cm9-N4IWM_kV9gVUMZ2xWmbrUg7UZe_LOWCjdpf238BRqTSHc_3U; access_token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2OTQzNzU5MzgsImlhdCI6MTY5NDIwMzEzOCwiaWQiOjIzOTA4ODkzNSwibmJmIjoxNjk0MjAzMTM4LCJyZXFfY3R4X2hhc2giOiJhYzdiYjU3MzUwYzVhYTBkNTgzYjg3YjE1ZTMzYmFkYiIsInR5cGUiOiJiZWFyZXIiLCJ1c2VyX2lkIjo0NjMwMDA4NH0.LssSlc5ULo62_8lofpCF9pPs_BFiJYsAEDgALTYZeZsQBDIhmJ3CWJ0Q98vWw8DBHeze-9ILsK5W4I6nnPHkNayUGeMees9c2Ig-Rh33QPJmkThuuljEticfVgYZCSxKVBAnMNL1u6YGHyJMkNhl2K_lqzImf0xd1sZuBWAoD1dRd6Zfe26gyV46CehUC61MWYw410nsGGrsjYXgq7pMesiNfI6-Qx5iOFf4Mm_2gUzZa2EKR8gyT9EoPWckEV_jolqyXa46QfkD87B6W1KytxWGSWXBSCMUK9rMUN-w9CTWq33SkA8tmmjCA1LmYIvxatt8f3tcLo0wvzCkSN91noH_q01J4zRBRI9rf7yPj9sTygq7x6Uv_GoaY0LAqO_s2OrbhDDXwqKP7KCm3ESlQG5DkwgfF_WywTSZ5TtT9B1C7V3_N8nymiD0EYMS_2IgAkAfyBL70F_kPV04TY0fI8Y7nrGT91mq3SJNM_C8RrRyYPlvnO8JMNzd9JC19eoJhU2-N7qNW7lkNFwGPBfMaQ2A1_MTCCDZ_PmXf-bhF380OnsV1JavIPyODsLrzyjnrtsF3dwv0eh7QeTqry2RGSlrx2knoeApniJcNXmDdKmAm2ANLUG-7Dj1a7jNfolTvQ0imnLo79ZeGNNStMvt8cSsgkXmJN7Q3EFz313qkRo',
#     'Connection': 'Upgrade',
#     'Sec-WebSocket-Version': '13',
#     'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits',
# }
cookies = {
    'jwt_auth': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE2OTUzMDUyMjQsIm5iZiI6MTY5NTMwNTIyNCwiZXhwIjoxNjk1MzkxNjI0LCJ1c2VyX2lkIjo0NjMwMDA4NCwiZW1haWwiOiJtYWdlc2htZ3IxQGdtYWlsLmNvbSJ9.CbjWYOSA7O2Bpl1yPM6TNCsMJ23ZulIJGMKHKXHKKu2aG_s7YGWZGdlyA8ikFDLAZtO7Sgr_1XiPmJcDAFv3IPWfQkQ6l6s8lWPa1dtQua0xOUiYIAbKDq63ueMYeoKpg-0bw6krnKREPGKxmXhpcUHjlH4-BO_hEjXv8E3h7s5YvGbyVbA4rNa2nBRkZm2UEs7myEmZmhaU-fKJyPSnSUTEPWkWWMkjn9giUxZj14WNTLejsMDDTUs3Y9MvRIbYUwTGt-Li6_4PB0JUxqwV1F2jtBCt2OUXdOlDyIfIwP2kGM1wQUATvVssJ5Ae50r_GxDjNgxOJhhmG37QCOCQWcpi2GQnlwhg3B6anmQ5otZ_NbFsKYXNIoPIbekB95gWZhEtRk_ntdt3ifiskMckZkvQz0EL-KYQ9nOb57er4YYyS0ZShKyOqCjhxwjNLVWhMIrFrVIbsoks_NMluWukjEq7ESRS17oyYYUu6WhOpE58OjWhCxQCYZUbqlOgxThbBpKmtF70M74vfxhH2-TJUjLOihyOJsGGuU15sn-iK5RVtSidujwjelbriTY_ySksrlj7dhhlv2Ewb2wHX7GGAbpieIXQmLRftfPVzdz3SfhOzf7BE0Vl5aeKWPfZj5029zuybW4YXSvVA7BuwBiROhXH1cY7TTGdbSX6hTCGO_Y',
    'access_token': 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2OTUzMTk2NTYsImlhdCI6MTY5NTE0Njg1NiwiaWQiOjI0MjY1OTkxNSwibmJmIjoxNjk1MTQ2ODU2LCJyZXFfY3R4X2hhc2giOiJjMjdkODg1ZTJjYzdlMzc4MjIxMTZkZTg2ZDRmNjAzZCIsInR5cGUiOiJiZWFyZXIiLCJ1c2VyX2lkIjo0NjMwMDA4NH0.vssozU5bvi3Oph3okK7GdpwZ0sLNvGfDkh1K8r3MVprWxj47aP8SJiWjP5mzsGNuuLkuvDiQXkAlBj8srz2Mkeu54MRrNDXiRrZGtCzkLu36CaMpcJI8JjZmtTRy9eej0OO_Q0N0XLBqq4fNwr_9iHRE_5MspW0Qb2RW4HQtjfHZhCU6-bG0Cgc5arhQe-Fc1NdzN5yqJL1Ocr40XRPln_-pTHF62KnnDKOpeAEk_cSE5TjpAmuIwSO2vfnCkzepty_m3N7AL9nMVuHazMhN3fOkLwnuRcGwtUAUnBtaD3Tf9bge5Hbu3CqHQP2NZJq-FQOMAk_ExolM6YidzgDYVqGj6-N9ZJou2jfVYcG0f_s3kDDWAEWGlppctfk1CQX5PxJxM1-nXxMO-nGHzOJGLA_ZEn8pi5rTgTgbGVhEuQ2ZHfLTYonNmIMxUeeNSIz806irLERIqKd1A502nCk_CYbuSxG3HU2_l13OS0JmWJTwOfmuKnUMgqWTgwI_w-RCegq8BDCoAbzsLg3RiDkamyHlc-tByG9xspkEZGpSfmfz-aFaY2_qmKrHb-HQOPVzhXLMi24ajwXoyiNDuq0Ub91SeptVysrYL40YR7LK_mP2t-zJNT4DjCqiz-qD96gKtWJNL5jziRMUvthzFS-hu4prgTh2BnRz8hf9VVdEbRw',
    }  
cookies_str = '; '.join([f"{key}={value}" for key, value in cookies.items()])
HEADERS = {'Cookie': 'session='+cookies_str, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}

OLYMP_WS = r"wss://ws.olymptrade.com/otp?cid_ver=1&cid_app=web%40OlympTrade%402023.3.20364%4020364&cid_device=%40%40desktop&cid_os=linux%40x86_64"

#############TRADING VIEW CONSTANTS################
EXCHANGE = 'FX_IDC'
SCREENER = 'forex'
EUR_SYMBOLS = ['EURUSD','EURCAD','EURGBP','EURJPY','EURAUD','EURCHF','EURNZD']
GBP_SYMBOLS = ['GBPUSD','GBPAUD','GBPCAD','GBPJPY','GBPCHF','GBPNZD']
CAD_SYMBOLS = ['CADJPY','CADCHF']
AUD_SYMBOLS = ['AUDJPY','AUDUSD','AUDCHF','AUDNZD','AUDCAD']
USD_SYMBOLS = ['USDCAD','USDJPY','USDCHF']

##############based on indian timings#################
#FROM 5.30AM TO 2.30PM
current_date_time = datetime.now(pytz.timezone('UTC')).astimezone(pytz.timezone('Asia/Kolkata'))
TIME_5_30 = datetime.now().replace(hour=5,minute=30)
TIME_14_30 = datetime.now().replace(hour=14,minute=30)
SYMBOLS_LIST_5_TO_2 = ['AUDNZD','AUDJPY','AUDUSD','USDJPY','GBPUSD','USDCHF']
#FROM 12.30PM TO 8.30PM
TIME_12_00 = datetime.now().replace(hour=12,minute=30)
TIME_8_30 = datetime.now().replace(hour=20,minute=30)
SYMBOLS_LIST_12_TO_8 = ['EURUSD','GBPUSD','USDJPY','USDCHF']
#FROM 5.30PM TO 2.30AM
TIME_17_30 = datetime.now().replace(hour=17,minute=30)
TIME_2_30 = datetime.now().replace(hour=2,minute=30)+timedelta(days=1)
SYMBOLS_LIST_17_TO_2 = ['AUDUSD','EURCAD','EURAUD', 'EURJPY', 'CADJPY']

TIME_SYMBOL_MAPPING = {
    (TIME_5_30, TIME_14_30): SYMBOLS_LIST_5_TO_2,
    (TIME_12_00, TIME_8_30): SYMBOLS_LIST_12_TO_8,
    (TIME_17_30, TIME_2_30): SYMBOLS_LIST_17_TO_2,
}
#####################TELEGRAM BOT CONSTANTS########################333

IMAGE_GREEN= cur_dir+'/backend/dolphin/images/green.jpg'
IMAGE_RED = cur_dir+'/backend/dolphin/images/red.jpg'

#telegram client
BOT_TOKEN = '6447275263:AAGewMLrHZJheq0zOR0M9DSptM6Ogan9JVg'
CHAT_ID = '883318761'
GROUP_ID = '-1001858529704'
##############################################################################