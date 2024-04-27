import pickle
from common.task import callorput
from tradingasset.models import *
from common.socketconnect.Olymptradeconnect import OlympTradeClient
from common.views import TradingViewApi
from common.constants import *
from datetime import *
from common.telegram_bot import send_telegram_message
from tradingview_ta.main import Interval
from django.utils import timezone
from django.http import HttpResponse
import pandas as pd
# from trading.celery import app
from django.shortcuts import render
import json
from TradingDataGenerate import main
from ta.trend import macd,cci,adx,macd_signal,adx_pos,adx_neg,sma_indicator,ema_indicator
from ta.momentum import rsi,stochrsi_d,stochrsi_k,stochrsi,williams_r
import numpy as np
import math
# Create your views here.
# value = list()
class OlympTradeTrigger:
    def __init__(self) -> None:
        # symbols,screener,exchange,interval
        balance_key = 'demo' #real
        self.olymp_client = OlympTradeClient(group='demo')
        self.balance = self.olymp_client.balance
        self.s = main.TvDatafeed('mageshragav1@gmail.com','Magesh1@')
        print(f"Current {balance_key} Balance is : {self.balance}")

    @staticmethod
    def calculate_1(pd: pd.DataFrame,predict=True):
        pdrsi = rsi(pd['close'],14)
        pdcci = cci(pd['high'],pd['low'],pd['close'],14)
        pdadx = adx(pd['high'],pd['low'],pd['close'])
        pdadx_pos = adx_pos(pd['high'],pd['low'],pd['low']) 
        pdadx_neg = adx_neg(pd['high'],pd['low'],pd['low'])
        pdmacd = macd(pd['close'])
        pdmacd_signal = macd_signal(pd['close'])
        pdstochrsi_d = stochrsi_d(pd['close'])
        pdstochrsi_k = stochrsi_k(pd['close'])
        pdstochrsi = stochrsi(pd['close'])
        pd2 = pd.iloc[:,1:7].copy(deep=True) # iloc[row,column]
        pd2['rsi'] = pdrsi
        pd2['cci'] = pdcci
        pd2['adx'] = pdadx
        pd2['adx_pos'] = pdadx_pos
        pd2['adx_neg'] = pdadx_neg
        pd2['macd'] = pdmacd
        pd2['macd_signal'] = pdmacd_signal
        pd2['stochrsi_d'] = pdstochrsi_d
        pd2['stochrsi_k'] = pdstochrsi_k
        pd2['stochrsi'] = pdstochrsi
        pd2['sma_av'] = sma_indicator(pd['close'],10)
        pd2['ema_av'] = ema_indicator(pd['close'],10)
        pd2['RSI'] = pdrsi.apply(lambda x: 1 if x < 30 else 2 if x > 70 else 0).astype('int32')
        pd2['ADX'] = np.where((pd2['adx'] > 25.00) & (pd2['adx_pos'] > pd2['adx_neg']), 1, np.where((pd2['adx'] > 25.00) & (pd2['adx_pos'] < pd2['adx_neg']), 2, 0)).astype('int32')
        pd2['MCAD'] = np.where((pd2['macd'] > pd2['macd_signal']), 1, np.where(pd2['macd'] < pd2['macd_signal'], 2, 0)).astype('int32')
        # pd2['next_close'] = pd2['close'].shift(-1)
        pd2.dropna(axis=0,inplace=True)
        pd2['SMA'] = np.where((pd2['sma_av'] > pd2['close']), 1,
                                np.where((pd2['sma_av'] < pd2['close']), 2, 0)).astype('int32')
        pd2['EMA'] = np.where((pd2['ema_av'] > pd2['close']), 1,
                                np.where((pd2['ema_av'] < pd2['close']), 2, 0)).astype('int32')
        pd2['Prediction'] = np.where((pd2['open'] < pd2['close']), 1,
                                np.where((pd2['open'] > pd2['close']), 2, 0)).astype('int32')
        pd2.drop(columns=['sma_av', 'ema_av'], inplace=True)
        return pd2
    
    @staticmethod
    def close_calculate(close):
        print(close)
        close = str(close).split('.')[-1]
        abs_tol = '.'+'2'.rjust(len(close),'0')
        print(f'abs values {abs_tol}')
        abs_tol = float(abs_tol)
        return abs_tol

    @staticmethod
    def confirm_trend(pddata: pd.DataFrame):
        ema_20 = ema_indicator(pddata['close'],window=20)
        ema_50 = ema_indicator(pddata['close'],window=50)
        rsi_14 = rsi(pddata['close'],14)
        abs_tol = OlympTradeTrigger.close_calculate(pddata['close'].iloc[-1])
        print(f'ema lst value {ema_20.iloc[-1],ema_50.iloc[-1]}')
        print(f'ema 2nd lst value {ema_20.iloc[-2],ema_50.iloc[-2]}')
        close_confirm_1 = math.isclose(ema_20.iloc[-1],ema_50.iloc[-1],abs_tol=abs_tol)
        close_confirm_2 = math.isclose(ema_20.iloc[-2],ema_50.iloc[-2],abs_tol=abs_tol)
        rsi_14_1 = rsi_14.iloc[-1]
        rsi_14_2 = rsi_14.iloc[-2]
        if close_confirm_1 and (50 < rsi_14_1 < 70):
            return 'BUY'
        elif close_confirm_1 and (50 > rsi_14_1 > 30):
            return 'SELL'
        elif close_confirm_2 and (50 < rsi_14_2 < 70):
            return 'BUY'
        elif close_confirm_2 and (50 > rsi_14_2 > 30):
            return 'SELL'
        else:
            return 'NEUTRAL'

    def get_candles(self,pair='EURUSD',size=60):
        data = self.olymp_client.get_candle(size=size,pair=pair) 
        candle_data = data[0].get('candles')
        pd_data = pd.DataFrame(candle_data)
        pd_data['t'] = pd.to_datetime(pd_data['t'], unit='s')
        pd_data.apply(lambda row: pd.Series(row),axis=1)
        return pd_data
        

    def start_trading(self, symbols='EURUSD'):
        import random
        for symbols in TRADE_SYMBOLS:
            callorput.apply_async(args=[symbols])

    def single_trigger(self,symbols='EURUSD'):
        try:
            five_min = Interval.INTERVAL_5_MINUTES
            olymptrade = OlympTrade()
            self.trading_signal = TradingViewApi(symbols=symbols,screener=SCREENER,exchange=EXCHANGE,interval='1m')
            signal = self.trading_signal.signal
            summary = self.trading_signal.get_summary(signal)
            summary['asset'] = symbols
            oscillator = self.trading_signal.get_oscillators(signal)
            mov_avg = self.trading_signal.get_moving_avg(signal=signal)
            indicators = self.trading_signal.get_indicators(signal=signal)
            print(oscillator)
            return oscillator,indicators
        except Exception as e:
            print(e.args)

    def multi_trigger(self):
        try:
            value = list()
            current_time = timezone.now().astimezone(pytz.timezone('America/New_York'))
            for timeing, assets in TIME_SYMBOL_MAPPING.items():
                recommend = self.single_trigger(symbols='EURUSD',countdown=3)
                return recommend
            return value
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
    value = trigger.start_trading()
    print(value)
    return HttpResponse(json.dumps(value))


def data_generation(*args, **kwargs):
    olymp = OlympTradeTrigger()
    print('started')
    data = sheet_upgrade()
    print('ended')
    return HttpResponse(json.dumps({'response': 'success','code': '0'}))

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
    import matplotlib.pyplot as plt
    import numpy as np
    from io import BytesIO
    import base64
    y = np.array([get_report['win'], get_report['loose'], get_report['draw']])
    mylabels = [f"WIN {get_report['win']}", f"LOOSE {get_report['loose']}", f"DRAW {get_report['draw']}"]
    plt.pie(y, labels = mylabels)
    # Save the plot to a memory buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()
    plot_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
    response = HttpResponse(content_type='image/png')
    response.write(base64.b64decode(plot_data))
    return response

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


def put_excel(data):
    import gspread
    from common.apiconnection.olymptradeapi import OlympTradeAPI
    from oauth2client.service_account import ServiceAccountCredentials
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
        ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name('backend/dolphin/google-credentials.json', scopes)
    gc = gspread.authorize(credentials)
    summary = gc.open_by_url('https://docs.google.com/spreadsheets/d/10_56aiY13RWM0abBk8Zq4JxNYkdlpzsom0FkZolZh3Q/edit?usp=sharing').worksheet('PREDICT')
    # Extract column names as headers
    headers = list(data.columns)

    # Convert DataFrame values to a list of lists
    values = data.values.tolist()

    # Update the first row with headers and subsequent rows with values
    summary.update('A1', [headers])
    # summary_list = list()
    # summary_list.append(data)
    summary.append_rows(values)
    return 'success'

def sheet_upgrade():
    import gspread
    from common.apiconnection.olymptradeapi import OlympTradeAPI
    from oauth2client.service_account import ServiceAccountCredentials
    trigger = OlympTradeTrigger()
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
        ]
    credentials = ServiceAccountCredentials.from_json_keyfile_name('backend/dolphin/google-credentials.json', scopes)
    gc = gspread.authorize(credentials)
    headers = ['datetime','open','close','low','high','RSI','STOCH.K','CCI','ADX','AO','Mom','MACD','Stoch.RSI','W%R','BBP','UO','PREDICTION']
    for i in EUR_SYMBOLS:
        summary = gc.open_by_url('https://docs.google.com/spreadsheets/d/1vZfmIKTySisbM92WCmXWEzHF1XOGtIiW9wMPRUG3Mw8/edit?usp=sharing').worksheet(i)
        summary.update('A1', [headers])
        oscillator,indicator = trigger.single_trigger(symbols=i)
        date_time = datetime.strftime(datetime.now(),'%Y-%m-%d %H:%M:%S')
        values = [date_time, indicator['open'],indicator['close'],indicator['low'],indicator['high'],
                  oscillator['COMPUTE']['RSI'],oscillator['COMPUTE']['STOCH.K'],oscillator['COMPUTE']['CCI'],oscillator['COMPUTE']['ADX'],oscillator['COMPUTE']['AO'],
                  oscillator['COMPUTE']['Mom'],oscillator['COMPUTE']['MACD'],oscillator['COMPUTE']['Stoch.RSI'],oscillator['COMPUTE']['W%R'],oscillator['COMPUTE']['BBP'],
                  oscillator['COMPUTE']['UO']]
        lrows = summary.get_all_values()
        print(f'{i} import Starting..!!!!')
        # Get the data from the last row
        last_row_data = summary.row_values(len(lrows))
        if last_row_data and last_row_data[1] != 'open':
            if float(last_row_data[1]) < indicator['open']:
                summary.update_cell(len(lrows),len(headers),1)
            elif float(last_row_data[1]) > indicator['open']:
                summary.update_cell(len(lrows),len(headers),2)
            else:
                summary.update_cell(len(lrows),len(headers),0)
        summary.append_row(values)
        print(f'{i} imported Successfully..!!!!')
    return True