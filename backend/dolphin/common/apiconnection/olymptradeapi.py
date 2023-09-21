import requests
from socketconnect.Olymptradeconnect import OlympTradeClient
from constants import *


class OlympTradeAPI:
    def __init__(self) -> None:
        self.wsconnection = OlympTradeClient()
        self.account_id = self.wsconnection.accountId
        self.account_group = self.wsconnection.accountGroup

    def getHistory(self):
        headers = {**HEADERS.copy(), **{'X-App-Version': '7673', 'X-Request-Project': 'bo', 'X-Request-Type': 'Api-Request', 'X-Requested-With': 'XMLHttpRequest'}}
        data = {"limit": 10, "group": self.account_group, "order": "time_close", "page": 1, "account_id": int(self.account_id)}
        return requests.post("https://api.olymptrade.com/v3/cabinet/deals-history",headers=headers,json=data).json()