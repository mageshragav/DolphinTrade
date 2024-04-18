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
    'access_token': 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3MTM1Mzc4MTAsImlhdCI6MTcxMzM2NTAxMCwiaWQiOjM4MTEyNTU2NSwibmJmIjoxNzEzMzY1MDEwLCJyZXFfY3R4X2hhc2giOiJiMWJlOWU0YjQ0ZjExZDViM2E1M2FhZmEyZmJhNTQ2YiIsInR5cGUiOiJiZWFyZXIiLCJ1c2VyX2lkIjo0NjMwMDA4NH0.TdvKhbG49PcRin2HRJ_CAS0snbP0RIuodgmfhtQW6_uXRCENfFPiVpkVg-Jq9Vw4wuEoSY1kRxbQ3lC-VlVd7MDuOwe6CEVvXpfyzwzeQDMwtw65pqj4L4dvz6Wxe0YNiglkNUZ1QpCQ9rplxwUJnrIA5r_e8pyumlnOf5FyTH60YG30prR_7oSOjlIWcW9gQwASlg6RZb3VkZ91RTC4DeFVwoumLk2_QAT2ZeW7-A7za6Cvkn4tYhNDk43zyg9PPKBmoVnDuDKRXZGlhqyxe1JYVe8Kqarx-OWGrj2pFH5JmbFRLeXVx1Y1DRWI3fQ4wiz-EbX7OwWTIPHuReWTAWQglSFUGEqZ6PwBNHrj96ZKBWr-QKEsfK6iRbn4iigHXVxlU-3s3GhhRul0a62aBqCWe1Kp5Gii_EBZ64qJcaWDZKBZexWF5moCrYGtJcboVYN0Eyq_0OAoUC8m0QiRJokZvwdpBczYDig4nfhsiTi9SF10wV5RkAc3J4WcWVyN2d-LkYyxkPxdrq-aWtw7MUEdk8BnIpdsbh08IiPmfUEyuYGlPZihMVrejMuy9b8x3gnVelGEilwNfmyfs-L2OcKOxtCB9G8H0TyGdH5y9v7QymLIYAR10Obvchf1A4P9GwOjszzyZdZi9Gxcf8cSwpSIoVvKOZ7JjDR0W_pHrKY',
    'jwt_auth': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3MTMzNjUwMTIsIm5iZiI6MTcxMzM2NTAxMiwiZXhwIjoxNzEzNDUxNDEyLCJ1c2VyX2lkIjo0NjMwMDA4NCwiZW1haWwiOiJtYWdlc2htZ3IxQGdtYWlsLmNvbSJ9.mNEf1-wEXz8sFd1hVtwCz1_jjnT6n4jQx5G5E60qUnSDHmh42JidJSAHCvkDMkbwhZeviSEkW7x5aow4GeTBeS2ipx8cdhLAucqOFEqM6nhYXOhRSdmPlvKY0PwoBWkeXxQucrOI_F4X4C3OXWyMKUxd6k2aXhrAO6fMQkTyWIyI7hGZ8z207iOFSZ2sPF5UzU7h9tuQZq1FwK-VN3nsvMeHWFb_KxzuRrbCVB4HlAAyT8_khW87dxFdbkLKMQLHZIfEAayZx8ux-xmMFTUeAYEtFLr4Dn8scCMIRS-LlErX52moO2E2xKoBnCuEWBmOmLi56ALPz0EKSnVPc3jTIPKy6KmjvgJJwWm5TdZ93g8J8ybOSJJFzHRyRMomi4KFLQtKTo3XUI34rs6XZ3oZ_NsH7qtxgSe4aJFz6NYBz8XTamgujR_gYL_ZKfY67PhOXJ6ugEQVEB9O2UnXNyiRpzIFKhbojc5J89uvVmSB0lh0UGJR5Z_x6tgjto_VHhOL5LDGTc-Qx7ag4WATtOltwv04gBxu5vqjusEzi-AqlydJ1Sps0w1crNDDcZE2u0TzSgAhZFJ6MAtSyEtJPDXDwNm--cfuHsMqS36ZUEIgozWQ-J6Nf4fCl8u4AFJhCsGVGRTmk2xxGYhA6u8C3WbDvVa0gq8piDbp4aW21b0pH5k',
    }  
cookies_str = '; '.join([f"{key}={value}" for key, value in cookies.items()])
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
# cookies_str = "'Cookie': 'guest_id=1000163614828235836441830584547061689779910043140201155559642052; __hstc=95761603.f2de272f989c05048cc39d36a27455e2.1689779911863.1689779911863.1689779911863.1; hubspotutk=f2de272f989c05048cc39d36a27455e2; _gcl_au=1.1.390423421.1689779917; _rdt_uuid=1689779917470.1538a053-37df-4cae-9c20-4d68eb5b1010; _scid=4b9fb4ab-6e0d-4d9c-97b5-d1675ed84588; _tt_enable_cookie=1; _ttp=VsIt3QMJYaEUvKVyIfbT2Jr9IHo; __exponea_etc__=2ce15ac4-a131-4833-8717-e584109f6a99; _sctr=1%7C1689739200000; _scid_r=4b9fb4ab-6e0d-4d9c-97b5-d1675ed84588; _ga=GA1.2.1373637290.1689779917; _ga_SN8XZNJ2M7=GS1.1.1689779917.1.1.1689780108.60.0.0; enterdate=2023-09-14+21%3A00%3A35; lang=en_US; checked=1; __cflb=0H28v9SCd6TDXBB3Aqm3oESsmV2UcyTkz4oMPYYhJjE; amp_fffbd0_olymptrade.com=JWltmevrgCidRd9-DHdw7q.MTgzZjFmNzEtMTUyNy00YTAyLTkyZDQtYWY5YzY3Mzg0Nzhj..1hbg1tuuj.1hbg1tuuj.5.1.6; tr_http_referer=af_siteid%3DLPL45-04en%26click_id%3Ddddc2e7e-16f6-4846-ad65-d7fc4633054a%26noapp%3D%26ref%3Dcpa_kf_1947474%26traffic%3D1%26utm_campaign%3D25%26utm_content%3D2NKZ%26utm_medium%3Dcpa%26utm_source%3D1947474%26utm_term%3D1947474; tr_request_uri=%2Fl%2FLPL45-04en%2Fcpa_kf_1947474%3Faf_siteid%3DLPL45-04en%26click_id%3Ddddc2e7e-16f6-4846-ad65-d7fc4633054a%26http_referer%3Daf_siteid%25253DLPL45-04en%252526click_id%25253Ddddc2e7e-16f6-4846-ad65-d7fc4633054a%252526noapp%25253D%252526ref%25253Dcpa_kf_1947474%252526traffic%25253D1%252526utm_campaign%25253D25%252526utm_content%25253D2NKZ%252526utm_medium%25253Dcpa%252526utm_source%25253D1947474%252526utm_term%25253D1947474%26noapp%3D%26ref%3Dcpa_kf_1947474%26traffic%3D1%26utm_campaign%3D25%26utm_content%3D2NKZ%26utm_medium%3Dcpa%26utm_source%3D1947474%26utm_term%3D1947474%26pixel%3D1; tr_traffic=%7B%22created_at%22%3A%222023-09-29+11%3A47%3A24%22%2C%22ref%22%3A%22cpa_kf_1947474%22%2C%22ref_channel%22%3A%22cpa%22%2C%22land%22%3A%22LPL45-04en%22%2C%22utm_campaign%22%3A%2225%22%2C%22utm_term%22%3A%221947474%22%2C%22utm_content%22%3A%222NKZ%22%2C%22utm_medium%22%3A%22cpa%22%2C%22utm_source%22%3A%221947474%22%2C%22guest_id%22%3A%221000163614828235836441830584547061689779910043140201155559642052%22%7D; __cf_bm=d5yeGkAWIjG6vhBEAYbFdvaKW14Pz7M5E9u3rz5rfiI-1695977504-0-AVPoywl/BLxJbMXe4r893jbArZT4VqOJqIdAcIvrYuEIg/u/y/lSK4ioJHbU8xUKLPCQoxh6gViTI4bLqoSM28c=; _cfuvid=ujHq7vvqfi9tw.eZNfNfCsSNvvEtwClQDkPJDq3Vp50-1695977504961-0-604800000; amp_fffbd0=JWltmevrgCidRd9-DHdw7q.MTgzZjFmNzEtMTUyNy00YTAyLTkyZDQtYWY5YzY3Mzg0Nzhj..1hbg1tsda.1hbg266a0.0.27.27; jwt_auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE2OTU5Nzc1MTIsIm5iZiI6MTY5NTk3NzUxMiwiZXhwIjoxNjk2MDYzOTEyLCJ1c2VyX2lkIjo0NjMwMDA4NCwiZW1haWwiOiJtYWdlc2htZ3IxQGdtYWlsLmNvbSJ9.g0HtaxdHy8e7qzjaMBaGWRE8U_LEvXtQpX1lX1CjxZJ9o40quUSUJzX6NlpLH7MtI_ItRPFXxK3Fa-B3kgcwKpLAlGbjb8BSslmBxfYUV1LvLtSvrs0tIKPoLIvaBn5LJ3Ytz7V7eEeBeeYcFtzAk-OWZwdiC-C01SAHnyQ0nNYNl4JiFVgd4QiTyJkHHkN535DsAphdlDeEqAVwmvoqqG5sNzv774JxpJhkGIXvtf8Ndv8_F8yflTOfoyWmo0x356qMl7d2SjcwfGpHwQJA2toyadmvf2Mvqh-kmmUl1YAydoLxrfoSnjojTJwpORiY4pgPNA8IVW6oUAzyZaZ9KGXSdi6G61UjrafDjKVgSs00cbVT7rtrOVLRLavdkHXJaWAgU1N4JD0xPl2FY93_EOXyqCddTPJpA53Bj7gHgGYm2JKJFgwOV6RhnGchAHUj5wiOvweairoRE_dE1sqqY6xtBbK-rTtMTm2cszP7ePf3UVbtUPpD24kyK_yiT_t6vGPL6Wld_M1KbuohmgDIioUE5ruJ_pYI70RKcTZD-n5u5Pb52xcULtvk41RW4GN_UEKFt2UgQ_yLC1PGFmmcYdPwJa_G9SByzCRKPT1Oq1BfjdpcuHuzc9ceeJP30Hvwsw7zShpuXWhNv6Fojn8P4hswUazGjGo40-nMUzRC8rU; access_token=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE2OTYxNTAzMTIsImlhdCI6MTY5NTk3NzUxMiwiaWQiOjI1NDQzNjg2NSwibmJmIjoxNjk1OTc3NTEyLCJyZXFfY3R4X2hhc2giOiJjMjdkODg1ZTJjYzdlMzc4MjIxMTZkZTg2ZDRmNjAzZCIsInR5cGUiOiJiZWFyZXIiLCJ1c2VyX2lkIjo0NjMwMDA4NH0.uGA5vrQrSO3-943R18Vi6M5fVrlKRDJ9u6E81pZOYlRr5W0LJ-ARxCPkDwOfFSAxyYZ0rSFN2HU75o6rHZr6wVzkaSHw3-z44hrSrAPIHcYGelVder0Uvt-49NUUP1P8d4g9Lfa_ROQVckmv6io1qUeCSDLvDxrclz2y46Ik2HPqPe8DQzHTrOguQ1VFIbxWfyFCRupniQMRMX111_81-VOyJvEr--wLZ0rtxN1NVQswF4PR_exBREtgSbq2EbwXhtkMgowDYbRE9K_6-q4dvY17u58Nk0o6L8vAWgzlN2rEy-Iz_sZUUQ-xKkKUx6QnOV_Wto0CAVfatAsKbaMQSnvcmQz_ewlEBmCpktjjDSMBIFBtpGO4LH1r3CAnK-sWDjXRyT1F_n3ZMHz-TjUXikuRryZc0lMFhBgaMUWs_TpmROwn9-lDXOelcllTmhbkVeTJCJH7OpFZNwDRZvCCDpbErTq4L7jOzb-GHr3t4hidIV8zXaM_qLc8HidFmyOHjaoQ_2WrB_-xn_gbnHzcpH4OuknI5JuCsqLCGbUl4S5oOKAbCyOhOC-9BiW1UydArmG8mOc2_t3TfAn2-s_QWsZwXbLbVeH6P6hQ72g-WVLwZbRxco73C40cXAWIOS-f-KvnV2EeJxaKy2kjFiNntsCtJEjGTu9DTQ0lk5gJjGo'"
HEADERS = {'Cookie': cookies_str, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}
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
OLYMP_WS = r"wss://ws.olymptrade.com/otp?cid_ver=1&cid_app=web%40OlympTrade%402023.3.20364%4020364&cid_device=%40%40desktop&cid_os=linux%40x86_64"

#############TRADING VIEW CONSTANTS################
EXCHANGE = 'FX_IDC'
SCREENER = 'forex'
EUR_SYMBOLS = ['EURUSD','EURJPY','EURGBP'] #'EURAUD' #,'EURJPY' #'EURGBP'
GBP_SYMBOLS = ['GBPUSD'] #,'GBPJPY'
CAD_SYMBOLS = ['CADJPY','CADCHF'] #'CADCHF'
AUD_SYMBOLS = ['AUDJPY','AUDUSD'] #,'AUDCHF','AUDNZD',
USD_SYMBOLS = ['USDCAD','USDJPY'] #'USDCHF'
# COMMON_SYMBOLS = GBP_SYMBOLS+EUR_SYMBOLS+CAD_SYMBOLS+AUD_SYMBOLS+USD_SYMBOLS
# COMMON_SYMBOLS = ['EURUSD','GBPUSD','AUDUSD','USDCAD','USDJPY','EURJPY','USDCAD'] #'EURGBP','GBPAUD','GBPCAD',
COMMON_SYMBOLS = ['EURUSD']
ALL_SYMBOLS = GBP_SYMBOLS+EUR_SYMBOLS+AUD_SYMBOLS
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

IMAGE_GREEN= cur_dir+'/backend/dolphin/images/green.jpg'
IMAGE_RED = cur_dir+'/backend/dolphin/images/red.jpg'

#telegram client
BOT_TOKEN = '6447275263:AAGewMLrHZJheq0zOR0M9DSptM6Ogan9JVg'
CHAT_ID = '883318761'
GROUP_ID = '-1001858529704'
##############################################################################