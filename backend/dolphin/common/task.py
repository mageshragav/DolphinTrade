import pickle
from common.constants import *
from datetime import *
from common.telegram_bot import send_telegram_message
import pandas as pd
from dolphin.celery import app as ap
from django.conf import settings
import logging
import numpy as np

logger = logging.getLogger('dolphin')
curr_dir = settings.BASE_DIR

# @ap.task
# def callorput(assest: str):
#     from tradingasset.views import OlympTradeTrigger
#     from tradingasset.models import OlympTrade
#     timing = '300'
#     call_timing = '900'
#     ml_model = pickle.load(open(f'{curr_dir}/common/ml_model/rfclassifier_new_{int(timing)//60}.sav','rb'))
#     ml_model2 = pickle.load(open(f'{curr_dir}/common/ml_model/xgbclassifier_new_{int(timing)//60}.sav','rb'))
#     # ml_model = pickle.load(open(f'{curr_dir}/common/ml_model/rfclassifier_{int(timing)//60}_1.sav','rb'))
#     # ml_model2 = pickle.load(open(f'{curr_dir}/common/ml_model/xgbclassifier_{int(timing)//60}_1.sav','rb'))
#     # tradingview_obj = main.TvDatafeed('mageshragav1@gmail.com','Magesh1@')
#     def change_dtype(key,value):
#         return int(value) if key in ['RSI','ADX','MCAD','SMA','EMA'] else value
#     for assest in [assest,]: #,'EURJPY','EURGBP','GBPUSD','AUDCAD','AUDJPY'
#         client = OlympTradeTrigger() 
#         # response_data = tradingview_obj.get_hist(symbol=assest,exchange='FX',interval=main.Interval.in_5_minute,n_bars=300,extended_session=False)
#         # one_min_data = tradingview_obj.get_hist(symbol=assest,exchange='FX',interval=main.Interval.in_1_minute,n_bars=300,extended_session=False)
#         # five_min_data = client.get_candles(pair='EURUSD_OTC',size=300)
#         five_min_data = client.get_candles(pair=assest,size=int(timing))
#         # response_data_15 = self.s.get_hist(symbol=symbols,exchange='FX',interval=main.Interval.in_15_minute,n_bars=300,extended_session=False)
#         result_pd = OlympTradeTrigger.calculate_1(five_min_data.iloc[::-1])
#         # logger.info(result_pd.iloc[-1])
#         data_1 = result_pd.iloc[-1,5:].to_dict()
#         data_1 = pd.DataFrame({key: [change_dtype(key,value)] for key, value in data_1.items()})
#         logger.info(f'\n{data_1}')
#         ml_output = ml_model.predict(data_1)
#         ml_output2 = ml_model2.predict(data_1)
#         logger.info(assest)
#         trend = OlympTradeTrigger.confirm_trend(result_pd,symbol=assest,duration=f'{int(timing)//60}m')
#         logger.info(f"assest {assest} and trend {trend} prediction data {ml_output[0]}, {ml_output2[0]}")
#         #summary['RECOMMENDATION'] in ('BUY', 'STRONG_BUY')
#         #summary['RECOMMENDATION'] in ('SELL', 'STRONG_SELL')
#         # ml_output = self.ml_model_15.predict(data_1)
#         if 1 == ml_output[0] and 1 == ml_output2[0] and trend == 'BUY':
#             if not OlympTrade.objects.filter(asset= assest, created_at__gte=datetime.now()-timedelta(seconds=int(call_timing))).exists():
#                 OlympTrade.objects.create(**{'asset': assest, 'created_at': datetime.now()})    
#                 msg = f'Recommended for next {int(call_timing)//60} min in {assest} was BUY'
#                 logger.info(msg)
#                 response = send_telegram_message.apply_async(args=(f"{curr_dir}{IMAGE_GREEN}", msg))
#                 response_data = client.olymp_client.get_bet('up',assest,amount='1',duration=f'{call_timing}')
#         elif 2 == ml_output[0] and 2 == ml_output2[0] and trend == 'SELL':
#             if not OlympTrade.objects.filter(asset= assest, created_at__gte=datetime.now()-timedelta(seconds=int(call_timing))).exists():
#                 OlympTrade.objects.create(**{'asset': assest, 'created_at': datetime.now()})
#                 msg = f'Recommended for next {int(call_timing)//60} min in {assest} was SELL'
#                 logger.info(msg)
#                 response = send_telegram_message.apply_async(args=(f"{curr_dir}{IMAGE_RED}", msg))
#                 response_data = client.olymp_client.get_bet('down',assest,amount='1',duration=f'{call_timing}')
#         else:
#             logger.info('NEUTRAL')
#         client.olymp_client.disconnect()

@ap.task
def callorput(assest: str):
    from tradingasset.views import OlympTradeTrigger
    from tradingasset.models import OlympTrade
    from TradingStradegy.mt4stradegies.fractelreversal import FractelReversal
    from TradingStradegy.mt4stradegies.extremespike import ExtremeSpike
    from TradingStradegy.mt4stradegies.TrendConfirm import TMIndicator

    try:
        # assest =assest+'_OTC'
        timing = '300'
        call_timing = '900'
        client = OlympTradeTrigger() 
        five_min_data = client.get_candles(pair=assest,size=int(timing))
        frstradegy_5_min = FractelReversal(five_min_data.iloc[::-1],assest)
        tm_ind_5_min = TMIndicator(five_min_data.iloc[::-1])
        extremestradegy_5_min = ExtremeSpike(five_min_data.iloc[::-1],assest)
        data = pd.concat([frstradegy_5_min.mainloop(), extremestradegy_5_min.mainloop(),tm_ind_5_min.mainloop()],axis=1)
        # Check if any of the specified columns have a value of 1
        extreme_buy = bool(data.iloc[-2][['line1', 'line2', 'line4', 'line5']].eq(-1).any().any())
        # Check if any of the specified columns have a value of -1
        extreme_sell = bool(data.iloc[-2][['line1', 'line2', 'line4', 'line5']].eq(1).any().any())
        # Check if any of the specified columns have a value of -1
        tm_ind_buy = bool(data.iloc[-2:]['BUY_TM'].any()) or bool(data.iloc[-2:][['up_arrow']].notna().any().any())
        tm_ind_sell = bool(data.iloc[-2:]['SELL_TM'].any()) or  bool(data.iloc[-2:][['dn_arrow']].notna().any().any())
        # buy,sell= data['BullishReversal'].iloc[-3:], data['BearishReversal'].iloc[-3:]
        # fractel_buy = any([True if i != 0 else False for i in buy])
        # fractel_sell = any([True if i != 0 else False for i in sell])
        ds_data = data.iloc[-5:][['t','line1', 'line2', 'line4', 'line5', "up_arrow", "dn_arrow",  "SELL_TM",  "BUY_TM"]]
        logger.info(f"{assest} and \n data {ds_data}")
        logger.info(f"assest {assest} and trend prediction data \n extreme buy {extreme_buy} sell {extreme_sell} \n and tm buy {tm_ind_buy} and tm sell {tm_ind_sell} ")
        if (extreme_buy and not extreme_sell) and (tm_ind_buy and not tm_ind_sell):
            if not OlympTrade.objects.filter(asset= assest, created_at__gte=datetime.now()-timedelta(seconds=int(call_timing))).exists():
                OlympTrade.objects.create(**{'asset': assest, 'created_at': datetime.now()})    
                msg = f'Recommended for next {int(call_timing)//60} min in {assest} was BUY'
                logger.info(msg)
                response = send_telegram_message.apply_async(args=(f"{curr_dir}{IMAGE_GREEN}", msg))
                response_data = client.olymp_client.get_bet('up',assest,amount='1',duration=f'{call_timing}')
        elif (extreme_sell and not extreme_buy) and (tm_ind_sell and not tm_ind_buy):
            if not OlympTrade.objects.filter(asset= assest, created_at__gte=datetime.now()-timedelta(seconds=int(call_timing))).exists():
                OlympTrade.objects.create(**{'asset': assest, 'created_at': datetime.now()})
                msg = f'Recommended for next {int(call_timing)//60} min in {assest} was SELL'
                logger.info(msg)
                response = send_telegram_message.apply_async(args=(f"{curr_dir}{IMAGE_RED}", msg))
                response_data = client.olymp_client.get_bet('down',assest,amount='1',duration=f'{call_timing}')
        else:
            logger.info('NEUTRAL')
        client.olymp_client.disconnect()
    except Exception as e:
        print(e.args)