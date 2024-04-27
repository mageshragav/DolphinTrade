import json
from websocket import create_connection
from websocket._exceptions import WebSocketConnectionClosedException
from common.socketkey.olymptradekey import OlympTradeConnection
from common.constants import HEADERS, OLYMP_WS
import time

class OlympTradeClient:
    def __init__(self, group='demo'):
        self.group = group
        self.ws = None
        self.connect()

    def connect(self):
        self.ws = create_connection(OLYMP_WS, header=HEADERS)
        self.key = OlympTradeConnection(group=self.group)
        self.balance = self.key.balance

    def disconnect(self):
        if self.ws:
            self.ws.close()

    def send_and_receive(self, data):
        if self.ws:
            try:
                self.ws.send(data)
                response = self.ws.recv()
                return json.loads(response)[0]['d']
            except WebSocketConnectionClosedException:
                self.connect()
        return False

    def get_bet(self, direction, pair, amount="1", duration="60"):
        bet_key = self.key.get_bet_key(dir=direction, pair=pair, amount=amount, duration=duration)
        print(bet_key)
        bet_key = json.dumps(bet_key)
        response = self.send_and_receive(bet_key)
        return response if response else False

    def get_onlive_bet(self):
        trace_key = self.key.get_on_live_bets()
        response = self.send_and_receive(trace_key)
        return response if response else False

    def get_wallet(self):
        wallet_key = self.key.get_wallet_key()
        response = self.send_and_receive(wallet_key)
        return response if response else False

    def get_history(self):
        history_key = self.key.get_history_key()
        response = self.send_and_receive(history_key)
        return response if response else False
    
    def get_candle(self,size=60,pair='EURUSD'):
        history_key = self.key.get_candle_data_key(pair='EURUSD')
        response = self.send_and_receive(history_key)
        return response if response else False