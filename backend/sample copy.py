from websocket import create_connection
from datetime import datetime, timedelta
import time
from random import randint
import json
cookie = '901b317a53bee6be5ae62c239cd858b81f84f4bb9e7ba8489f8de081131580cb2f253d863a2632fc11daef2a7dded1741fe4335fd320939e954372d1a95a788e885bb088786f153d14a1ab11c689e84b04f94d46f4bd26e05aa6b2076783cfba84fcc72ae2cf66f98c0f8f4a38369a184a567c6a2db498eaa4a60137b419d92dab2ae466d356d006512d0d1c5c5966d1e3f40694bed54197a5f0cd6dc64f11e8bbb06a60bb5b8cf390f8c02a5f527be443611c3faac703cf4f1b74d33961b0de6ba412f1dc7b47f74d3619e62c31c6b69f2c677786fbced1f97984f2fbb846e23e10d65c73769dfdca7326075e7ae0d83713a94783e33612e82a6a7bf7355035691d305caa3e80b91a0d333f7b7e05db'
headers = {
    'Origin': 'https://iqoption.com',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
    'identity': cookie,
}
ws = create_connection("wss://ws.iqoption.com/echo/websocket",header=headers)
print(ws.connected)
# asset = "EURUSD_otc"
# price = 1.0
# duration = 1
# direction = "call"
# is_demo = 1
# option_type = 100
# import calendar
# import time
# request_id = int(str(time.time()).split('.')[1])
def date_to_timestamp(dt):
    # local timezone to timestamp support python2 pytohn3
    return time.mktime(dt.timetuple())
def get_expiration_time(timestamp, duration):
    #
    now_date = datetime.fromtimestamp(timestamp)
    exp_date = now_date.replace(second=0, microsecond=0)
    if (int(date_to_timestamp(exp_date+timedelta(minutes=1)))-timestamp) > 30:
        exp_date = exp_date+timedelta(minutes=1)

    else:
        exp_date = exp_date+timedelta(minutes=2)
    exp = []
    for _ in range(5):
        exp.append(date_to_timestamp(exp_date))
        exp_date = exp_date+timedelta(minutes=1)

    idx = 50
    index = 0
    now_date = datetime.fromtimestamp(timestamp)
    exp_date = now_date.replace(second=0, microsecond=0)
    while index < idx:
        if int(exp_date.strftime("%M")) % 15 == 0 and (int(date_to_timestamp(exp_date))-int(timestamp)) > 60*5:
            exp.append(date_to_timestamp(exp_date))
            index = index+1
        exp_date = exp_date+timedelta(minutes=1)

    remaning = []

    for t in exp:
        remaning.append(int(t)-int(time.time()))

    close = [abs(x-60*duration) for x in remaning]

    return int(exp[close.index(min(close))]), int(close.index(min(close)))
exp, idx = get_expiration_time(
            int(time.time()), 60)
# if idx < 5:
#     option = 3  # "turbo"
# else:
#     option = 1  # "binary"
# option = 3
# exp = time.time() + 2 * 60
# data = {
#     "body": {"price": price,
#                 "active_id": 76,
#                 "expired": int(exp),
#                 "direction": "call",
#                 "option_type_id": option,
#                 "user_balance_id": int(1161500337)
#                 },
#     "name": "binary-options.open-option",
#     "version": "2.0"
# }
# 1695544761
# 1695544788
expiry = int((datetime.now()+timedelta(minutes=1)).timestamp())
buy_msg = {"name":"sendMessage",
           "request_id":"246",
           "local_time":"56569",
           "msg":{
               "name":"binary-options.open-option",
               "version":"2.0",
               "body":{
                   "user_balance_id":f"{1161500337}",
                   "active_id":"76",
                   "option_type_id":"3",
                   "direction":"call",
                   "expired":f"{exp}",
                   "refund_value":0,
                   "price":"1.0",
                   "value":"1084105",
                   "profit_percent":"86"
                   }
                }
            }
msg = {
            "name": "sendMessage",
            "request_id": randint(1000,10000),
            "body": {"price": 1.0,
                     "active_id": 76,
                     "expired": int(exp),
                     "direction": "call",
                     "option_type_id": 3,
                     "user_balance_id": int(1161500337),
                     },
            "name": "binary-options.open-option",
            "version": "2.0"
        }
print('json data')
print(ws.recv())
print('json data')
ws.send(json.dumps(buy_msg))
ws.send(json.dumps(msg))
# msg = {
#             "body": {"price": 1.0,
#                      "active_id": 76,
#                      "expired": int(exp),
#                      "direction": "call",
#                      "option_type_id": 3,
#                      "user_balance_id": int(1161500337),
#                      },
#             "name": "binary-options.open-option",
#             "version": "2.0"
#         }
# name = "sendMessage"
# request_id = randint(1000,10000)
# data = json.dumps(dict(name=name, msg=msg, request_id=str(request_id)))
# """
data = {    "name": "sendMessage",
            "request_id": randint(1000,10000),
            "body": {"price": 1.0,
                     "active_id": 76,
                     "expired": int(exp),
                     "direction": 'put',
                    "option_type_id":'3',
                    "user_balance_id":int(1161500337)
                     },
            "name": "binary-options.open-option",
            "version": "1.0"
        }
ws.send(json.dumps(data))
# {"name":"sendMessage","request_id":"1659","local_time":1292840,"msg":{"name":"binary-options.open-option","version":"2.0","body":{"user_balance_id":1161500337,"active_id":76,"option_type_id":3,"direction":"put","expired":1697900460,"refund_value":0,"price":1.0,"value":1083915,"profit_percent":86}}}