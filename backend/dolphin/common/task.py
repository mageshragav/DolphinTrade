import pickle
from common.constants import *
from datetime import *
from common.telegram_bot import send_telegram_message
import pandas as pd
from celery import app
from TradingDataGenerate import main
import os
from django.conf import settings

curr_dir = settings.BASE_DIR

@app.shared_task()
def callorput(assest: str):
    from tradingasset.views import OlympTradeTrigger
    from tradingasset.models import OlympTrade
    client = OlympTradeTrigger()
    ml_model = pickle.load(open(f'{curr_dir}/common/ml_model/rfclassifier_5.sav','rb'))
    ml_model2 = pickle.load(open(f'{curr_dir}/common/ml_model/xgbclassifier_5.sav','rb'))
    tradingview_obj = main.TvDatafeed('mageshragav1@gmail.com','Magesh1@')
    def change_dtype(key,value):
        return int(value) if key in ['RSI','ADX','MCAD','SMA','EMA'] else value
    # response_data = tradingview_obj.get_hist(symbol=assest,exchange='FX',interval=main.Interval.in_5_minute,n_bars=300,extended_session=False)
    # one_min_data = tradingview_obj.get_hist(symbol=assest,exchange='FX',interval=main.Interval.in_1_minute,n_bars=300,extended_session=False)
    one_min_data = client.get_candles(pair='EURUSD_OTC',size=300)
    # response_data_15 = self.s.get_hist(symbol=symbols,exchange='FX',interval=main.Interval.in_15_minute,n_bars=300,extended_session=False)
    result_pd = OlympTradeTrigger.calculate_1(one_min_data.iloc[::-1])
    # print(result_pd.iloc[-1])
    data_1 = result_pd.iloc[-1,4:-1].to_dict()
    data_1 = pd.DataFrame({key: [change_dtype(key,value)] for key, value in data_1.items()})
    print(data_1)
    ml_output = ml_model.predict(data_1)
    ml_output2 = ml_model2.predict(data_1)
    print(assest)
    trend = OlympTradeTrigger.confirm_trend(one_min_data.iloc[::-1])
    print(f"assest {assest} and {trend} prediction data {ml_output[0]}, {ml_output2[0]}")
    #summary['RECOMMENDATION'] in ('BUY', 'STRONG_BUY')
    #summary['RECOMMENDATION'] in ('SELL', 'STRONG_SELL')
    # ml_output = self.ml_model_15.predict(data_1)
    if ml_output[0] == 1 and ml_output2[0] == 1 and trend == 'BUY':
        if not OlympTrade.objects.filter(asset= assest, created_at__gte=datetime.now()-timedelta(minutes=5)).exists():
            OlympTrade.objects.create(**{'asset': assest, 'created_at': datetime.now()})
            msg = f'Recommended for next 15 min in {assest} was BUY'
            print(msg)
            response = send_telegram_message.apply_async(args=(f"{curr_dir}{IMAGE_GREEN}", msg))
            response_data = client.olymp_client.get_bet('up',assest,amount='1',duration='300')
    elif ml_output[0] == 2 and ml_output2[0] == 2 and trend == 'SELL':
        if not OlympTrade.objects.filter(asset= assest, created_at__gte=datetime.now()-timedelta(minutes=5)).exists():
            OlympTrade.objects.create(**{'asset': assest, 'created_at': datetime.now()})
            msg = f'Recommended for next 15 min in {assest} was SELL'
            print(msg)
            response = send_telegram_message.apply_async(args=(f"{curr_dir}{IMAGE_RED}", msg))
            response_data = client.olymp_client.get_bet('down',assest,amount='1',duration='300')
    else:
        print('neutral')
    client.olymp_client.disconnect()
