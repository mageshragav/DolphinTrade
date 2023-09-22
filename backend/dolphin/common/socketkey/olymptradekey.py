import random
import time
import string
import json
# from websocket import create_connection
import websocket
from common.constants import HEADERS, OLYMP_WS

class OlympTradeConnection():
    def __init__(self,group='demo') -> None:
        self.host_v6 = OLYMP_WS
        self.headers = HEADERS
        key = 1 if group == 'demo' else 0
        self.wallet = self.get_connection()
        self.balance = self.wallet[key]['amount']
        self.account_id = self.wallet[key]['account_id']
        self.group_id = group

    def get_connection(self):
        ws = websocket.create_connection(self.host_v6,header=self.headers)
        key = str(self.get_wallet_key()).replace("'","\"").replace(" ","")
        ws.send(key)
        print(key)
        print('[{"t":2,"e":98,"uuid":"'+self.generateUuid()+'","d":[54]}]')
        data = json.loads(ws.recv())
        ws.close()
        return data[0]['d']
        # ws = create_connection(self.host_v6,header=self.headers)
        # try:
        #     ws.send(self.get_wallet_key())
        #     print("after sending connection")
        #     data = json.loads(ws.recv())
        #     return data[0]["d"]
        # except:
        #     ws.close()

    def generateUuid(self):
        return ''.join([random.choice(string.ascii_uppercase+string.digits) for n in range(18)])
    
    def get_bet_key(self,dir,pair,amount="1",duration="300"):
        data = [{"t":2,"e":23,"uuid":f"{self.generateUuid()}","d":[{"amount":int(amount),"dir":str(dir),"pair":str(pair),"cat":"digital","pos":0,"source":"platform","account_id":int(self.account_id),"group":"demo","timestamp":int(time.time()),"risk_free_id":None,"duration":int(duration)}]}]
        return data
    
    def get_wallet_key(self):
        data = [
            {"t":2,
             "e":98,
             "uuid":f"{self.generateUuid()}",
             "d":[54]
            }
        ]
        return data
    
    def get_on_live_bets(self):
        data = [
            {
                "t": 2,
                "e": 31,
                "uuid": self.generateUuid(),
                "d": [
                    {
                        "account_id": self.account_id,
                        "group": self.group_id,
                    }
                ]
            }
        ]
        return f'{data}'
    
    def get_currency_key(self):
        data = [
            {
                "t": 2,
                "e": 98,
                "uuid": self.generateUuid(),
                "d": [70]
            }
        ]
        return f'{data}'
    
    def get_history_key(self):
        data = {
            "limit": 10,
            "group": self.group_id,
            "order": "time_close",
            "page": 1,
            "account_id": int(self.accountId)
        }
        return f'{data}'
    
    def get_connection_key(self):
        data = [
                {"t":2,
                 "e":98,
                 "uuid":self.generateUuid(),
                 "d":[54]
                }
            ]
            
        
        return f'{data}'