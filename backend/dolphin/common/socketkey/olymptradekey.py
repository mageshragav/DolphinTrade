import random
import time
import string
import json
# from websocket import create_connection
import websocket
from common.constants import HEADERS, OLYMP_WS, OLYMP_ORIGIN, OLYMP_EXTENSIONS
import logging

logger = logging.getLogger('dolphin')
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
        ws = websocket.create_connection(self.host_v6, header=self.headers,
                                         origin=OLYMP_ORIGIN,
                                         extensions=OLYMP_EXTENSIONS)
        key = str(self.get_wallet_key()).replace("'","\"").replace(" ","")
        ws.send(key)
        logger.info(key)
        logger.info('[{"t":2,"e":98,"uuid":"'+self.generateUuid()+'","d":[54]}]')
        # [{"t":2,"e":31,"uuid":"nTF3CI","d":[{"account_id":2073645904,"group":"real"}]}]
        data = json.loads(ws.recv())
        ws.close()
        return data[0]['d']
        # ws = create_connection(self.host_v6,header=self.headers)
        # try:
        #     ws.send(self.get_wallet_key())
        #     logger.info("after sending connection")
        #     data = json.loads(ws.recv())
        #     return data[0]["d"]
        # except:
        #     ws.close()

    def generateUuid(self,size=18):
        if size == 6:
            return ''.join([random.choice(string.ascii_uppercase+string.ascii_lowercase) for n in range(size)])
        return ''.join([random.choice(string.ascii_uppercase+string.digits) for n in range(size)])
    
    def get_bet_key(self, dir, pair, amount="1", duration="60"):
        """Binary / fixed trade (verified against the live platform format)."""
        data = [{"t":2,"e":23,"uuid":f"{self.generateUuid()}",
                 "d":[{"amount":int(round(float(amount))),"dir":str(dir),"pair":str(pair),
                       "cat":"digital","pos":0,"source":"platform",
                       "account_id":int(self.account_id),"group":self.group_id,
                       "timestamp":int(time.time()*1000),"risk_free_id":None,
                       "is_flex":False,"duration":int(duration)}]}]
        return data

    @staticmethod
    def _sl_tp(level):
        """Broker-exact SL/TP shape: {"value": <price>, "type": "price"}
        (no trailing field - matches the live platform capture)."""
        if level is None:
            return None
        if isinstance(level, dict):
            return {'value': level.get('value'), 'type': level.get('type', 'price')}
        return {'value': level, 'type': 'price'}

    def get_order_key(self, dir, pair, amount="1", multiplicator=100,
                      stop_loss=None, take_profit=None):
        """Multiplier trade (verified against the live platform format)."""
        data = [{"t":2,"e":1032,"uuid":f"{self.generateUuid()}",
                 "d":[{"amount":int(round(float(amount))),"multiplicator":int(multiplicator),
                       "dir":str(dir),"pair":str(pair),
                       "stop_loss":self._sl_tp(stop_loss),
                       "take_profit":self._sl_tp(take_profit),
                       "group":self.group_id,"account_id":int(self.account_id)}]}]
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
    
    def get_candle_data_key(self,pair='EURUSD',size=60):
        data = [
            {"t":2,
             "e":10,
             "uuid":self.generateUuid(size=6),
             "d":[{"pair":pair,"size":60,"to":int(time.time()),"solid":True}]}]
        # return f'{data}'.replace('True','true')
        return '[{"t":2,"e":10,"uuid":"'+self.generateUuid(size=6)+'","d":[{"pair":"'+pair+'","size":'+str(size)+',"to":'+str(int(time.time()))+',"solid":true}]}]'