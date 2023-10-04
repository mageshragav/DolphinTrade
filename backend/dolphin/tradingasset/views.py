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
            oscillator = self.trading_signal.get_oscillators(signal)
            mov_avg = self.trading_signal.get_moving_avg(signal=signal)
            indicators = self.trading_signal.get_indicators(signal=signal)
            recommend = self.trading_signal.personal_recommendation(data=summary,oscillator=oscillator, indicator=indicators)
            msg = self.message_generator(signal_value=summary,asset=symbols,indicators=indicators,moving_avg=mov_avg)
            if recommend['BUY']:
                response_data = self.olymp_client.get_bet('up',symbols,amount='1',duration='300')
                response = send_telegram_message.apply_async(args=(IMAGE_GREEN, msg))
                data = {'personal': 'BUY','direction': 'up','asset': symbols, 'amount': '1', 'duration': '300'}
                self.db_entry(summary=summary,mov_avg=mov_avg,indicators=indicators,data=data, oscillator=oscillator)
                # print(response_data)
                
            elif recommend['SELL']:
                response_data = self.olymp_client.get_bet('down',symbols,amount='1',duration='300')
                response = send_telegram_message.apply_async(args=(IMAGE_RED, msg))
                data = {'personal': 'SELL','direction': 'down','asset': symbols, 'amount': '1', 'duration': '300'}
                self.db_entry(summary=summary,mov_avg=mov_avg,indicators=indicators,data=data, oscillator=oscillator)
                # print(response_data)
            summary['RSI'] = indicators['RSI']
            summary['MACD'] = oscillator['COMPUTE']['MACD']
                
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
        return msg
    
def table_request(request):
    trigger = OlympTradeTrigger()
    value = trigger.multi_trigger() 
    # summary['personal'] = recommond
    # global value
    # value.append(summary)
    print(value)
    return HttpResponse(json.dumps(value))
    # return render(request,'table.html',context={"rows":value})