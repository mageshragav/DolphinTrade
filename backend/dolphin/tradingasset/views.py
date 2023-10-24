from tradingasset.models import *
from common.socketconnect.Olymptradeconnect import OlympTradeClient
from common.views import TradingViewApi
from common.constants import *
from datetime import *
from common.telegram_bot import send_telegram_message
from tradingview_ta.main import Interval
from django.utils import timezone
from django.http import HttpResponse
# from trading.celery import app
from django.shortcuts import render
import json
# Create your views here.
# value = list()
class OlympTradeTrigger:
    def __init__(self) -> None:
        # symbols,screener,exchange,interval
        balance_key = 'demo' #real
        self.olymp_client = OlympTradeClient(group='demo')
        self.balance = self.olymp_client.balance
        print(f"Current {balance_key} Balance is : {self.balance}")
        pass

    def db_entry(self,summary,mov_avg,indicators, data, oscillator):
        try:
            recomend = 1 if data['personal'] == 'BUY' else 2 if data['personal'] == 'SELL' else 3
            direction = 1 if data['direction'] == 'up' else 2
            olymp_data = {"asset": data['asset'],"personal_recommend": data['personal'], "recommend": recomend,
                        "recommend_buy": summary['BUY'], 'recommend_sell': summary['SELL'], 'recommend_neutral': summary['NEUTRAL'],
                        "price": data['amount'], "timing": data['duration'], "direction": direction}
            five_min = timezone.now()-timedelta(minutes=5)
            if not OlympTrade.objects.filter(asset=data['asset'], created_at__range=[five_min,timezone.now()]).exists():
                olymptrade = OlympTrade.objects.create(**olymp_data)
                moving_avg_data = {"olymptrade": olymptrade, "recommend": recomend, "recommend_buy": mov_avg['BUY'],
                                "recommend_sell": mov_avg['SELL'], "all_mvavg": json.dumps(mov_avg)}
                moving_avg = MovingAvg.objects.create(**moving_avg_data)
                indicators_data = {"olymptrade": olymptrade, "open": indicators['open'], "close": indicators['close'], "low": indicators['low'],
                                "high": indicators['high'], "indictors": json.dumps(indicators)}
                indicators_obj = Indicators.objects.create(**indicators_data)
                oscilator_recommend = 1 if oscillator['RECOMMENDATION'] in ('BUY', 'STRONG_BUY') else 2 if oscillator['RECOMMENDATION'] in ('SELL','STRONG_SELL') else 3
                oscillator_data = {"olymptrade": olymptrade, "recommended": oscilator_recommend, "buy": oscillator['BUY'],
                                "sell": oscillator['SELL'], "neutral": oscillator['NEUTRAL'], "oscillators": json.dumps(oscillator['COMPUTE'])}
                oscillator_obj = Osclillators.objects.create(**oscillator_data)
            else:
                print('trade will not accept for last five minutes')
            return True
        except Exception as e:
            print(e.args)
            return False
    def single_trigger(self,symbols='EURUSD'):
        try:
            five_min = Interval.INTERVAL_5_MINUTES
            olymptrade = OlympTrade()
            self.trading_signal = TradingViewApi(symbols=symbols,screener=SCREENER,exchange=EXCHANGE,interval=five_min)
            signal = self.trading_signal.signal
            summary = self.trading_signal.get_summary(signal)
            summary['asset'] = symbols
            oscillator = self.trading_signal.get_oscillators(signal)
            mov_avg = self.trading_signal.get_moving_avg(signal=signal)
            indicators = self.trading_signal.get_indicators(signal=signal)
            recommend = self.trading_signal.personal_recommendation(data=summary,oscillator=oscillator, indicator=indicators,mv=mov_avg)
            msg = self.message_generator(signal_value=summary,asset=symbols,indicators=indicators,moving_avg=mov_avg)
            # response = send_telegram_message.apply_async(args=('', msg))
            if recommend['BUY']:
                response_data = self.olymp_client.get_bet('up',symbols,amount='1',duration='300')
                response = send_telegram_message.apply_async(args=(IMAGE_GREEN, msg))
                data = {'personal': 'BUY','direction': 'up','asset': symbols, 'amount': '1', 'duration': '300'}
                self.db_entry(summary=summary,mov_avg=mov_avg,indicators=indicators,data=data, oscillator=oscillator)
                # print(response_data)
                print(f"================TRADING SUCCESS WITH BUY {symbols}=======================")
                print(symbols,summary,oscillator,indicators,mov_avg)
                print('================TRADING SUCCESS WITH BUY END=======================')
            elif recommend['SELL']:
                response_data = self.olymp_client.get_bet('down',symbols,amount='1',duration='300')
                response = send_telegram_message.apply_async(args=(IMAGE_RED, msg))
                data = {'personal': 'SELL','direction': 'down','asset': symbols, 'amount': '1', 'duration': '300'}
                self.db_entry(summary=summary,mov_avg=mov_avg,indicators=indicators,data=data, oscillator=oscillator)
                print(f"================TRADING SUCCESS WITH SELL {symbols}=======================")
                print(symbols,summary,oscillator,indicators,mov_avg)
                print('================TRADING SUCCESS WITH SELL END=======================')
                # print(response_data)
            summary['RSI'] = indicators['RSI']
            summary['MACD'] = oscillator['COMPUTE']['MACD']
            oscillator.update(indicators)
            mv_ag = mov_avg['COMPUTE']
            oscillator.update(mv_ag)
            summary['TOTAL'] = json.dumps(oscillator)
                
            return summary, recommend
        except Exception as e:
            print(e.args)

    def multi_trigger(self):
        try:
            value = list()
            current_time = timezone.now().astimezone(pytz.timezone('America/New_York'))
            for timeing, assets in TIME_SYMBOL_MAPPING.items():
                if timeing[0] <= current_time.replace(tzinfo=None) <= timeing[1]:
                    for asset in assets:
                        five_min = timezone.now() - timedelta(minutes=5)
                        if not OlympTrade.objects.filter(asset=asset, created_at__range=[five_min,timezone.now()]).exists():
                            summary, recommend = self.single_trigger(symbols=asset)
                            if recommend['SELL'] or recommend['BUY']:
                                summary['asset'] = asset
                                summary['personal'] = recommend
                                summary['date_time'] = timezone.now().strftime("%d/%m/%Y %H:%M:%S")
                                value.append(summary)
                    self.olymp_client.disconnect()
            return value
            # else:
            #     for asset in EUR_SYMBOLS:
            #         summary, recommend = self.single_trigger(symbols=asset)
            #         summary['asset'] = asset
            #         summary['personal'] = recommend
            #         value.append(summary)
        except Exception as e:
            print(e.args)


    def message_generator(self,signal_value, asset,indicators,moving_avg):
        current_date = datetime.now().strftime("%Y-%m-%d")
        five_min = (datetime.now()+timedelta(minutes=5)).strftime("%H:%M:%S")
        current_time = datetime.now().strftime("%H:%M:%S")
        asset_val = asset
        buy_value = signal_value['BUY']
        sell_value = signal_value['SELL']
        neutral_value = signal_value['NEUTRAL']
        recommend = signal_value['RECOMMENDATION']
        open = indicators['open']
        moving_ag = moving_avg['RECOMMENDATION']
        recommendation = f"Recommendation are buy {buy_value}, sell {sell_value}, neutral_value {neutral_value} and moving average was {moving_ag}"
        msg = f"In the upcoming {5} minutes from {current_time} on {current_date},opening price {open} and PUT {recommend} for the {asset_val} asset. {recommendation}"
        # html_css_content = """
        #     <html>
        #         <head>
        #             <style>
        #                 body {
        #                 font-family: Arial, sans-serif;
        #                 background-color: #f2f2f2;
        #                 }

        #                 .signal-card {
        #                 background-color: #fff;
        #                 border-radius: 10px;
        #                 box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        #                 width: 300px;
        #                 margin: 20px auto;
        #                 padding: 20px;
        #                 }

        #                 h1 {
        #                 color: #333;
        #                 font-size: 24px;
        #                 margin: 0;
        #                 }

        #                 .signal-info {
        #                 margin-top: 10px;
        #                 }

        #                 .info-label {
        #                 font-weight: bold;
        #                 margin-right: 5px;
        #                 }

        #                 .buy {
        #                 color: #4CAF50;
        #                 }

        #                 .sell {
        #                 color: #F44336;
        #                 }

        #                 .mov-avg {
        #                 margin-top: 10px;
        #                 }

        #                 .strong-buy {
        #                 background-color: #4CAF50;
        #                 color: #fff;
        #                 padding: 5px 10px;
        #                 border-radius: 5px;
        #                 }     
        #             </style>
        #         </head>"""+\
        #         f"""<body>
        #             <div class="signal-card">
        #                 <h1>SIGNAL: {recommend}</h1>
        #                 <div class="signal-info">
        #                 <span class="info-label">SYMBOL:</span> {asset_val}<br>
        #                 <span class="info-label">TIME:</span> {5} MINS<br>
        #                 <span class="info-label">OPEN:</span> {open}<br>
        #                 <span class="info-label">OSCILLATOR:</span>
        #                 <span class="buy">BUY: {buy_value}</span>
        #                 <span class="sell">SELL: {sell_value}</span><br>
        #                 </div>
        #                 <div class="mov-avg">
        #                 <span class="info-label">MOV AVG:</span> <span class="strong-buy">{moving_ag}</span>
        #                 </div>
        #             </div>
        #         </body>"""+\
        #     """</html>
        # """
        html_css_content =f"SIGNAL: {recommend}\n"+\
                f"SYMBOL: {asset_val}\n"+\
                f"TIME: 5 MINS\n"+\
                f"OPEN: {open}\n"+\
                f"RECOMMANDED SIGNALS:\n"+\
                f"BUY: {buy_value}\n"+\
                f"SELL: {sell_value}\n"+\
                f"MOV AVG: {moving_ag}"

        return html_css_content
    
def table_request(request):
    trigger = OlympTradeTrigger()
    value = trigger.multi_trigger()
    # summary['personal'] = recommond
    # global value
    # value.append(summary)
    print(value)
    return HttpResponse(json.dumps(value))
    # return render(request,'table.html',context={"rows":value})

def get_report(request):
    import gspread
    from common.apiconnection.olymptradeapi import OlympTradeAPI
    from oauth2client.service_account import ServiceAccountCredentials
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
        ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name('backend/dolphin/google-credentials.json', scopes)
    gc = gspread.authorize(credentials)
    s = OlympTradeAPI()
    date_time = datetime.now()
    date_str = date_time.strftime("%d/%m/%Y, %H:%M:%S")
    get_report = s.get_profit_lose_analysis(date_time)
    summary = gc.open_by_url('https://docs.google.com/spreadsheets/d/10_56aiY13RWM0abBk8Zq4JxNYkdlpzsom0FkZolZh3Q/edit?usp=sharing').worksheet('summary')
    summary_list = list()
    summary_list.append([date_str,get_report['total_trade'],get_report['win'],get_report['loose'],get_report['draw'],get_report['win_ratio'],get_report['loose_ratio'],get_report['trade_open'],get_report['trade_close']])
    summary.append_rows(summary_list)
    return HttpResponse("Success")

def get_detail_report(request):
    import gspread
    from dateutil.parser import parse
    from common.apiconnection.olymptradeapi import OlympTradeAPI
    from oauth2client.service_account import ServiceAccountCredentials
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
        ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name('backend/dolphin/google-credentials.json', scopes)
    gc = gspread.authorize(credentials)
    s = OlympTradeAPI()
    date_time = datetime.now()
    summary_list = list()
    date_str = date_time.strftime("%d/%m/%Y, %H:%M:%S")
    get_reports = s.get_detail_analysis(date_time)
    summary = gc.open_by_url('https://docs.google.com/spreadsheets/d/10_56aiY13RWM0abBk8Zq4JxNYkdlpzsom0FkZolZh3Q/edit?usp=sharing').worksheet('details')
    column_values = summary.col_values(4)
    last_row_value = column_values[-1]
    summary_list.append(['PAIR', 'DIR', 'STATUS', 'TIME_OPEN', 'TIME_CLOSE', 'OPEN', 'CLOSE', 'TEST_RESULT'])
    if last_row_value != 'TIME_OPEN':
        date_time = parse(last_row_value)
    summary.clear()
    for get_report in get_reports:
        summary_list.append([get_report['pair'],get_report['dir'],get_report['status'],get_report['time_open'],get_report['time_close'], get_report['open'],get_report['close'],get_report['test_result']])
    print(last_row_value)
    print(type(last_row_value))
    summary.append_rows(summary_list)
    return HttpResponse("Success")