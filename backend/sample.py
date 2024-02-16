import websocket
import rel


cookie = 'referer=https%3A%2F%2Fwww.google.com%2F; OTCTooltip={%22value%22:false}; lang=en; _ga=GA1.1.921205885.1697447414; z=[[%22graph%22%2C2%2C0%2C0%2C0.8333333]]; nas=[%22EURUSD_otc%22%2C%22AUDCAD_otc%22%2C%22USDCAD%22%2C%22USDCAD_otc%22]; remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d=eyJpdiI6IkZmei9QcHg1WUVsNHNBeFd0ZjdJWkE9PSIsInZhbHVlIjoiYlJ2YlhIbkdnSiszME4wdjVBZkxBaWMyKzdlSVhxSExBRDY3U0dNMVJXZG5SZG1Vc3NIQ1Y5QXhIQzZ2UForTkp1am9vWmQ4Wk1namNtYXdmaXhJUXE1ZWsxWDNmWEcxRHpDc1hscEhCNTN6aU95NksrY2tPcmtaWDNqd0NnTUwzQTVFQVE2QWZkeWZnQU9CVE5IdExwZXNJQ1JPeFlLMW1qS3pldlNYUG1CNXp4cFEwbHJmNWRMZndLU1RCNXFJd3hpcmYvUEgwTEovM29BM2twZTVUeHN3YVRsU3dZVlIxbkdmVjFpb0lRUGZHSzQxYnFyTHNvU0I1VjBIY2V0VSIsIm1hYyI6ImJmOTRmOGQ1MWYxMDRhZjQyMGRjYTc3YTM4NDNjOWQ4ZDJjMGZiZGVjNGIzNDUxNjU3ZDY4MDRjNWU0YjNmNzEiLCJ0YWciOiIifQ%3D%3D; _ga_L4T5GBPFHJ=GS1.1.1697454717.2.1.1697456983.0.0.0; __cf_bm=aEGDJGByzHdjuLvi4MoyeD9RZF_BrrYNGE4I8AsM4X0-1697969847-0-ARBWYIkgRtwCbAFHW0D8ocu8ZgnE5wKr1Iy6C+lSgbNnZocQqTAnBX52zDJ6eG8sUvhhlNFiMWZxXwQXAVUt1Lo=; _cfuvid=C7slSbj1KvEBpREvb.FJ8MmsjwBf48nk8JGowsE8StA-1697969847473-0-604800000; __vid1=40872a9a501f7b7bfd5b6554deb0248a; cf_clearance=N9WDnPe5vOuemGYCbLp8FhXSrebRY87DQzt1t9rOomk-1697969856-0-1-b7f587de.7fecd64f.e0f4d83e-0.2.1697969856; __vid_l3=f0b04263-d790-404d-b677-0acfddebcf40; laravel_session=eyJpdiI6IjF2dWk1UEhrYUhNckp4b1pETzVFalE9PSIsInZhbHVlIjoid2FFeXhPaUQ0UDJCdm1mOW9PQWdRTXMvUDJjTkpxNFhRTGh6VnhicGZQL2hITkJiQ2FUQTdNZUl3a1Q3eHpIUHA1RjVzQlp1YnZpd2padm5BT3FaWjRxeHAvbmFUY29wODgwa1J0Z1l1R3EvbFJuNzBLT3lqSDhxOFVXVlU2QmoiLCJtYWMiOiIwODYwOGFkMWYzYjhlYTAzOGE0MmFlZjE3MWU3YWYwMDZmNzUxYmQ1MTYzNmQ0MDlkZDk5YWE3NTM0ODhlZWE1IiwidGFnIjoiIn0%3D; last_trade=eyJpdiI6IitxTjN1bVAyaDA1d2dWYkZpUUhadWc9PSIsInZhbHVlIjoiaEsyNk5mQnBBVU1vL2U5Rkh4b045NG45TXBVVWlvK0JGYTkyZ0RyUnMrQ0xwVmg1OVVVclByR29NdkVmZEl3diIsIm1hYyI6IjcwMWQ3YzQyNDZmMzc1NTZkZGMzZmRmY2FiMjZiZDRhMmRjMWUyNjNmZTY3Nzg0ZWFkYzA0MjVkNTkzMjNkYWUiLCJ0YWciOiIifQ%3D%3D; demo=eyJpdiI6Inp5blZJYUtQRUFiTHlvSG5UVnkxR1E9PSIsInZhbHVlIjoiZExuTFdkN29xUnFiZ3Mzbzd4SFVTZkV4bitidE1oUGk3OUZ3SDhVZWtVRysvUWpRSDhKOTJkbkEvSUlidkprLyIsIm1hYyI6IjQwMGNhOTliN2I1OTk4YTFkNmNiNzE2ZjQ1ZDhkNzUwOWMxOGY4ZTliYzlhOTFlYjFjNTdhNjgzMzdlMTMyMTMiLCJ0YWciOiIifQ%3D%3D'
headers = {
    'Pragma': 'no-cache',
    'Origin': 'https://qxbroker.com',
    'Accept-Language': 'en-US,en;q=0.9',
    'Sec-WebSocket-Key': 'h6fbteJdYm4Imi89OurVbw==',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
    'Upgrade': 'websocket',
    'Cache-Control': 'no-cache',
    'Connection': 'Upgrade',
    'Sec-WebSocket-Version': '13',
    'Sec-WebSocket-Extensions': 'permessage-deflate; client_max_window_bits'
}
cookies = {
    'referer': 'https%3A%2F%2Fwww.google.com%2F',
    'OTCTooltip': '{%22value%22:false}',
    'lang': 'en',
    '_ga': 'GA1.1.921205885.1697447414',
    'nas': '[%22EURUSD_otc%22%2C%22AUDCAD_otc%22%2C%22USDCAD%22%2C%22USDCAD_otc%22]',
    'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d': 'eyJpdiI6IkZmei9QcHg1WUVsNHNBeFd0ZjdJWkE9PSIsInZhbHVlIjoiYlJ2YlhIbkdnSiszME4wdjVBZkxBaWMyKzdlSVhxSExBRDY3U0dNMVJXZG5SZG1Vc3NIQ1Y5QXhIQzZ2UForTkp1am9vWmQ4Wk1namNtYXdmaXhJUXE1ZWsxWDNmWEcxRHpDc1hscEhCNTN6aU95NksrY2tPcmtaWDNqd0NnTUwzQTVFQVE2QWZkeWZnQU9CVE5IdExwZXNJQ1JPeFlLMW1qS3pldlNYUG1CNXp4cFEwbHJmNWRMZndLU1RCNXFJd3hpcmYvUEgwTEovM29BM2twZTVUeHN3YVRsU3dZVlIxbkdmVjFpb0lRUGZHSzQxYnFyTHNvU0I1VjBIY2V0VSIsIm1hYyI6ImJmOTRmOGQ1MWYxMDRhZjQyMGRjYTc3YTM4NDNjOWQ4ZDJjMGZiZGVjNGIzNDUxNjU3ZDY4MDRjNWU0YjNmNzEiLCJ0YWciOiIifQ%3D%3D',
    '_ga_L4T5GBPFHJ': 'GS1.1.1697454717.2.1.1697456983.0.0.0',
    '__vid1': '40872a9a501f7b7bfd5b6554deb0248a',
    'demo': 'eyJpdiI6Inp5blZJYUtQRUFiTHlvSG5UVnkxR1E9PSIsInZhbHVlIjoiZExuTFdkN29xUnFiZ3Mzbzd4SFVTZkV4bitidE1oUGk3OUZ3SDhVZWtVRysvUWpRSDhKOTJkbkEvSUlidkprLyIsIm1hYyI6IjQwMGNhOTliN2I1OTk4YTFkNmNiNzE2ZjQ1ZDhkNzUwOWMxOGY4ZTliYzlhOTFlYjFjNTdhNjgzMzdlMTMyMTMiLCJ0YWciOiIifQ%3D%3D',
    'cf_clearance': 'J57wh9HGrHdciPpO7jEzP3TLbWOhpAFUr8RfuJxktyg-1697972036-0-1-b7f587de.13007bfd.e0f4d83e-0.2.1697972036',
    'z': '[[%22graph%22%2C2%2C0%2C0%2C0.071136]]',
    '__cf_bm': 'DXGFJO_WKnIZrKsA1kY_p1E54LecWQ8wpvzbicHrbDM-1697973880-0-AWBg6AqVPhRr4YYKu2zgyOlkHYjCQVVPgjHNLxTvEJaDnHxP+6Jvdo11DbmoMqveVpiY2ca6xdbU1rROC8aB004=',
    '_cfuvid': 'miTX8vI8ya0D2MnL3Vp28Bkgy170Yja.fkGOq_W18zo-1697973880581-0-604800000',
    'laravel_session': 'eyJpdiI6IjB0bWxjZ1VFTTRTZlQ4WGcvSGIxSkE9PSIsInZhbHVlIjoiOUFGOUNGUnVBR0YwckpxWnptcDVLdDlTTHlIUWQwZ0lSdFJpdGREWmtIRms3Q3NNelNFVDZhV0JoaUVYdGlGZ2o4bE5jNy9pUS9LUDFXNy8rUUQrU3RubldFZFlWc2Zha1RXVTh0ZllnOUlYdGFHU1dGUG9kdjg2YjRWNmF6U0kiLCJtYWMiOiJjNWQ2MzBiYzFiNDliMGE2NGU1NDgzMjZiMWNjMjBiZjhjOThkNGUyZTM0YThhOGRmOTk0NDVhZWNlYzAyYjI0IiwidGFnIjoiIn0%3D',
    'last_trade': 'eyJpdiI6InQwWkw2UjVOTjYvTDJpZWpCSWNHSEE9PSIsInZhbHVlIjoiQ1FweURNMWFxUDF1QWhvS0JpTG1pUDBaNlQ3ZDNrZXF2bDFVZVlueVhaaHJ3K2g5UWQyaVRuejVIWVFsUXdGZCIsIm1hYyI6IjU2ZjZlYjA0NjU5YWRhNWZjZWRiMmY4ZjAzNDRmYjZlMmQyN2JmYzBlNWEyNzhlNTBhNzQ0OTVlMGY4MmZkMmQiLCJ0YWciOiIifQ%3D%3D',
    '__vid_l3': 'd5440780-db9a-4b9c-a034-2f6bbe0d36c7',
}

cookies_str = '; '.join([f"{key}={value}" for key, value in cookies.items()])
# def on_message(ws,msg):
#     print('on message start')
#     key = '42["orders/open",{"asset":"USDCAD_otc","amount":70,"time":60,"action":"call","isDemo":1,"tournamentId":0,"requestId":1697972205,"optionType":100}]'
#     ws.send(key)
#     print('on message end')

# def on_error(ws,error):
#     print('on_error start')
#     print(error)
#     print('on_error end')

# def on_close(ws,error,msg):
#     print('on_close start')
#     print(error)
#     print(msg)
#     print('on_close end')
# ws = websocket.WebSocketApp(r"wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket",
#                           on_message = on_message,
#                           on_error = on_error,
#                           on_close = on_close,
#                           header=headers,
#                           cookie = cookies_str
# )
websocket.enableTrace(True)
import json
ws = websocket.WebSocket()
ws.connect(r"wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket",
           header=headers,cookie = cookies_str)
count = 0
ws.send('42["authorization",{"session":"8oSETfyWyNq3G1H3CKqW7oNmO2MjGOOSx0owM325","isDemo":1,"tournamentId":0}]')
payload = {
    "asset": "USDCAD_otc",
    "amount": 70,
    "time": 60,
    "action": "call",
    "isDemo": 1,
    "tournamentId": 0,
    "requestId": 1697972205,
    "optionType": 100
}

data = f'42["orders/open",{json.dumps(payload)}]'
ws.send(data)
# ws.run_forever()
key = '42["orders/open",{"asset":"USDCAD_otc","amount":70,"time":60,"action":"call","isDemo":1,"tournamentId":0,"requestId":1697972205,"optionType":100}]'
ws.send(key)
# ws.send()

