import requests
from common.socketkey.olymptradekey import OlympTradeConnection
from common.socketconnect.Olymptradeconnect import OlympTradeClient
from common.constants import *
from fractions import Fraction

class OlympTradeAPI:
    def __init__(self,group='demo') -> None:
        self.wsconnection = OlympTradeConnection()
        self.account_id = self.wsconnection.account_id
        self.account_group = group

    def getHistory(self,date_time=None):
        """
        [
            {
                "id": 7711986455,
                "user_id": 46300084,
                "account_id": 2747795093,
                "group": "demo",
                "cat": "digital",
                "amount": 1,
                "balance_change": -1,
                "currency": "usd",
                "pair": "EURUSD",
                "dir": "down",
                "status": "loose",
                "winperc": 82,
                "duration": 300,
                "time_open": 1696863172.02,
                "time_close": 1696863472.02,
                "time_close_default": 1696863472.02,
                "time_course_open": 1696863169.462,
                "curs_open": 1.05399,
                "curs_strike": 1.05399,
                "curs_close": 1.05443,
                "riskfree": false,
                "is_time": false,
                "refunded": false,
                "flat_protection_point_limit": 1
            },
        ]
        """
        # {
        # "account_id": 2747795093,
        # "cursor": "",
        # "limit": 20,
        # "pairs": ["AUDUSD"],
        # "closed_from": 1696824000,
        # "closed_to": 1696910399
        # }
        data = {"limit": 100, "account_id": int(self.account_id), "cursor": ""}
        if date_time is not None:
            from_timestamp = (date_time.replace(hour=1,minute=0)).timestamp()
            to_timestamp = (date_time.replace(hour=23,minute=59)).timestamp()
            data.update({"closed_from":from_timestamp,"closed_to":to_timestamp})
        # data = {"limit": 70, "account_id": int(self.account_id), "cursor": ""}
        return requests.post("https://gw.olymptrade.com/api/history/deals/ftt/v1",headers=DEALS_HEADERS,json=data).json()
    
    def get_profit_lose_analysis(self,date_time=None):
        get_analysis = dict()
        get_results = dict()
        get_result = self.getHistory(date_time)
        win_count = 0
        loose_count = 0
        draw_count = 0
        for i in get_result['deals']:
            get_analysis[i['pair']] = list() if not get_analysis.get(i['pair']) else get_analysis[i['pair']]
            win_count += 1 if i['status'] == 'win' else 0
            loose_count += 1 if i['status'] == 'loose' else 0
            draw_count += 1 if i['status'] == 'flat' else 0
            dictionary = {'direction': i['dir'],
                          'status': i['status'],
                          'duration': i['duration'],
                          'open': i['curs_open'],
                          'close': i['curs_close']}
            get_analysis[i['pair']].append(dictionary)
        get_results['win_count'] = win_count
        get_results['loose_count'] = loose_count
        get_results['draw_count'] = draw_count
        get_results['Profit'] = win_count - loose_count
        return get_analysis, get_results
    
    def get_detail_analysis(self,date_time=None):
        get_analysis = list()
        get_result = self.getHistory(date_time)
        for i in get_result['deals']:
            result = dict()
            result['pair'] = i['pair']
            result['dir'] = i['dir']
            result['status'] = i['status']
            result['time_open'] = f"{datetime.utcfromtimestamp(i['time_open'])}"
            result['time_close'] = f"{datetime.utcfromtimestamp(i['time_close'])}"
            result['open'] = i['curs_open']
            result['close'] = i['curs_close']
            result['test_result'] = 'draw'
            if i['status'] == 'loose':
                result['test_result'] = 'failure'
            elif i['status'] == 'win':
                result['test_result'] = 'success'
            get_analysis.append(result)
        return get_analysis
    