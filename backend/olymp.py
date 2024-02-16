from dolphin.common.apiconnection.olymptradeapi import OlympTradeAPI
from dolphin.common.constants import HEADERS,OLYMP_WS
from datetime import datetime

s = OlympTradeAPI()
date_time = datetime.now()
print(s.get_profit_lose_analysis(date_time))