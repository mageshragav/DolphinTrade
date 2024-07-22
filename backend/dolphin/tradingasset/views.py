from TradingStradegy.mt4stradegies import binary_arrows, super_signals, super_signals_v3, tm_indicator
from common.task import callorput
from tradingasset.models import *
from common.socketconnect.Olymptradeconnect import OlympTradeClient
from common.views import TradingViewApi
from common.constants import *
from datetime import *
from tradingview_ta.main import Interval
from django.utils import timezone
from django.http import HttpResponse
import pandas as pda
# from trading.celery import app
from django.shortcuts import render
import json
from ta.trend import macd,cci,adx,macd_signal,adx_pos,adx_neg,sma_indicator,ema_indicator, MACD
from ta.momentum import rsi,stochrsi_d,stochrsi_k,stochrsi,williams_r
import numpy as np
import pandas as pd
import logging


logger = logging.getLogger('dolphin')
# Create your views here.
# value = list()
class OlympTradeTrigger:
    def __init__(self) -> None:
        # symbols,screener,exchange,interval
        balance_key = 'demo' #real
        self.olymp_client = OlympTradeClient(group='demo')
        # self.balance = self.olymp_client.balance
        # # self.s = main.TvDatafeed('mageshragav1@gmail.com','Magesh1@')
        # logger.info(f"Current {balance_key} Balance is : {self.balance}")
    @staticmethod
    def indicatorCalculations(data_1 : pd.DataFrame):
        data = data_1.copy()
        data['LOCAL'] = pd.to_datetime(data['datetime']) - timedelta(hours=5)
        data['GMT'] = pd.to_datetime(data['datetime']) + timedelta(hours=2)
        b_arrow = binary_arrows.BinaryArrowSignalPredictor(data.iloc[::-1].reset_index(drop=True)).run()
        # extreme_b = extreme_binary.ExtremeBinarySignalPredictor(data).run() # works only in 15 mins chart
        # spike_e = extreme_spike.ExtremeSpikeSignalPredictor(b_arrow.iloc[::-1]).run()
        # arrow_imm = iim_arrows.IINWMARROWSSignalPredictor(spike_e).run()
        # arrow_super = super_arrows.SuperArrowSignalPredictor(spike_e).run()
        super_sig = super_signals.SuperSignalPredictor(b_arrow).run()
        super_sig_v3 = super_signals_v3.SuperV3SignalPredictor(super_sig).run()
        new_data = tm_indicator.TMIndicator(super_sig_v3).run()
        # # Check that all predictors return DataFrames with the same index
        # data_frames = [data.iloc[:, :8], b_arrow, spike_e, arrow_imm, arrow_super, super_sig, super_sig_v3, tmind]
        # # Ensure all DataFrames have the same index
        # for df in data_frames:
        #     if not df.index.equals(data.index):
        #         df.index = data.index
        # new_data = pd.concat(data_frames, axis=1)
        new_data['next_close'] = new_data['close'].shift(-3)
        # new_data = pd.concat([data.iloc[:,:8],b_arrow,spike_e,arrow_imm,arrow_super,super_sig,super_sig_v3,tmind])
        return new_data
    # @staticmethod
    # def calculate_1(pd: pd.DataFrame,predict=True):
    #     pdrsi = rsi(pd['close'],14)
    #     pdcci = cci(pd['high'],pd['low'],pd['close'],14)
    #     pdadx = adx(pd['high'],pd['low'],pd['close'])
    #     pdadx_pos = adx_pos(pd['high'],pd['low'],pd['low']) 
    #     pdadx_neg = adx_neg(pd['high'],pd['low'],pd['low'])
    #     pdmacd = macd(pd['close'])
    #     pdmacd_signal = macd_signal(pd['close'])
    #     pdstochrsi_d = stochrsi_d(pd['close'])
    #     pdstochrsi_k = stochrsi_k(pd['close'])
    #     pdstochrsi = stochrsi(pd['close'])
    #     pd2 = pd.iloc[:,1:7].copy(deep=True) # iloc[row,column]
    #     pd2['rsi'] = pdrsi
    #     pd2['cci'] = pdcci
    #     pd2['adx'] = pdadx
    #     pd2['adx_pos'] = pdadx_pos
    #     pd2['adx_neg'] = pdadx_neg
    #     pd2['macd'] = pdmacd
    #     pd2['macd_signal'] = pdmacd_signal
    #     pd2['stochrsi_d'] = pdstochrsi_d
    #     pd2['stochrsi_k'] = pdstochrsi_k
    #     pd2['stochrsi'] = pdstochrsi
    #     pd2['sma_av3'] = sma_indicator(pd['close'],3)
    #     pd2['sma_av6'] = sma_indicator(pd['close'],6)
    #     pd2['RSI'] = pdrsi.apply(lambda x: 1 if x < 30 else 2 if x > 70 else 0).astype('int32')
    #     pd2['ADX'] = np.where((pd2['adx'] > 25.00) & (pd2['adx_pos'] > pd2['adx_neg']), 1, np.where((pd2['adx'] > 25.00) & (pd2['adx_pos'] < pd2['adx_neg']), 2, 0)).astype('int32')
    #     pd2['MCAD'] = np.where((pd2['macd'] > pd2['macd_signal']), 1, np.where(pd2['macd'] < pd2['macd_signal'], 2, 0)).astype('int32')
    #     # pd2['next_close'] = pd2['close'].shift(-1)
    #     pd2.dropna(axis=0,inplace=True)
    #     pd2['SMA3'] = np.where((pd2['sma_av3'] > pd2['close']), 1,
    #                             np.where((pd2['sma_av3'] < pd2['close']), 2, 0)).astype('int32')
    #     pd2['SMA6'] = np.where((pd2['sma_av6'] > pd2['close']), 1,
    #                             np.where((pd2['sma_av6'] < pd2['close']), 2, 0)).astype('int32')
    #     pd2['Prediction'] = np.where((pd2['open'] < pd2['close']), 1,
    #                             np.where((pd2['open'] > pd2['close']), 2, 0)).astype('int32')
    #     pd2.drop(columns=['sma_av3', 'sma_av6'], inplace=True)
    #     return pd2
    
    def calculate_1(pddata: pd.DataFrame, predict=True):
        # Add indicators to new DataFrame
        pddata = pddata.copy()
        pddata.loc[:,'datetime'] = pd.to_datetime(pddata['t'])
        pd2 = OlympTradeTrigger.indicatorCalculations(pddata)
        signals = ['datetime','open','high','low','close','next_close',
                    'BinaryArrow',
                    'SuperSignalV3','TMSignal','LOCAL','GMT']
        predit_signals = [
        'BinaryArrow',
        'SuperSignalV3'
        ]
        pd2[predit_signals] = pd2[predit_signals].shift(1)
        pd2.to_csv('/tmp/olymp.csv')
        pd2 = pd2[signals]
        return pd2
    @staticmethod
    def close_calculate(close):
        logger.info(close)
        close = str(close).split('.')[-1]
        abs_tol = '.'+'4'.rjust(len(close),'0')
        logger.info(f'abs values {abs_tol}')
        abs_tol = float(abs_tol)
        return abs_tol

    @staticmethod
    def fractals_pandas(df, period=5):
        df = pda.DataFrame(df, columns=['high', 'low'])
        df['up'] = False
        df['down'] = False

        half_period = period // 2

        # Define conditions for a fractal up
        conditions_up = True
        for i in range(1, half_period + 1):
            conditions_up &= (df['high'] > df['high'].shift(i)) & (df['high'] > df['high'].shift(-i))
            # conditions_up &= (df['high'] > df['high'].shift(-i))

        # Define conditions for a fractal down
        conditions_down = True
        for i in range(1, half_period + 1):
            conditions_down &= (df['low'] < df['low'].shift(i)) & (df['low'] < df['low'].shift(-i))
            # conditions_down &= (df['low'] < df['low'].shift(-i))

        # Apply conditions to the dataframe
        df.loc[conditions_up, 'up'] = True
        df.loc[conditions_down, 'down'] = True

        result = df[['up', 'down']].values.tolist()
        return result
    
    # @staticmethod
    # def confirm_trend(df: pda.DataFrame, symbol='EURUSD',duration='5m') -> str:
    #     df = df.copy()
    #     tm_ind_5_min = TMIndicator(df)
    #     extremestradegy_5_min = ExtremeSpike(df,symbol)
    #     mv_ind_5_min = MovAvg(df)
    #     data = pd.concat([extremestradegy_5_min.mainloop(),tm_ind_5_min.mainloop(),mv_ind_5_min.mainloop()],axis=1)
    #     # Check if any of the specified columns have a value of 1
    #     extreme_buy = bool(data.iloc[-2][['line1', 'line2', 'line4', 'line5']].eq(-1).any())
    #     # Check if any of the specified columns have a value of -1
    #     extreme_sell = bool(data.iloc[-2][['line1', 'line2', 'line4', 'line5']].eq(1).any())
    #     # Check if any of the specified columns have a value of -1
    #     tm_ind_buy = bool(data.iloc[-2]['BUY_TM'])
    #     tm_ind_sell = bool(data.iloc[-2]['SELL_TM'])
    #     mv_ind_buy = bool(data.iloc[-2][['CrossUp']].notna().any())
    #     mv_ind_sell = bool(data.iloc[-2][['CrossDown']].notna().any())
    #     ds_data = data.iloc[-5:][['t','GMT','line1', 'line2', 'line4', 'line5',"SELL_TM",  "BUY_TM", "CrossUp", 'CrossDown']]
    #     logger.info(f"{symbol} and \n data {ds_data}")
    #     logger.info(f"assest {symbol} and trend prediction data \n extreme buy {extreme_buy} sell {extreme_sell} \n and tm buy {tm_ind_buy} and tm sell {tm_ind_sell} and {mv_ind_buy} and {mv_ind_sell}")
        
    #     if (tm_ind_buy or extreme_buy or mv_ind_buy) and not (tm_ind_sell and extreme_sell and mv_ind_sell):
    #         return 'BUY'
    #     elif (tm_ind_sell or extreme_sell or mv_ind_sell) and not (tm_ind_buy and extreme_buy and mv_ind_buy):
    #         return 'SELL'
    #     else:
    #         return 'NEUTRAL'

    def get_candles(self,pair,size=60):
        data = self.olymp_client.get_candle(size=size,pair=pair) 
        candle_data = data[0].get('candles')
        pd_data = pda.DataFrame(candle_data)
        pd_data['t'] = pda.to_datetime(pd_data['t'], unit='s')
        pd_data.apply(lambda row: pda.Series(row),axis=1)
        return pd_data
        

    def start_trading(self, symbols='EURUSD'):
        import random
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
            logger.info(oscillator)
            return oscillator,indicators
        except Exception as e:
            logger.info(e.args)

    def multi_trigger(self):
        try:
            value = list()
            current_time = timezone.now().astimezone(pytz.timezone('America/New_York'))
            for timeing, assets in TIME_SYMBOL_MAPPING.items():
                recommend = self.single_trigger(symbols='EURUSD',countdown=3)
                return recommend
            return value
        except Exception as e:
            logger.info(e.args)


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
    logger.info(value)
    return HttpResponse(json.dumps(value))


def data_generation(*args, **kwargs):
    olymp = OlympTradeTrigger()
    logger.info('started')
    data = sheet_upgrade()
    logger.info('ended')
    return HttpResponse(json.dumps({'response': 'success','code': '0'}))

def get_report(request):
    import gspread
    from common.apiconnection.olymptradeapi import OlympTradeAPI
    from oauth2client.service_account import ServiceAccountCredentials
    # scopes = [
    #     'https://www.googleapis.com/auth/spreadsheets',
    #     'https://www.googleapis.com/auth/drive'
    #     ]
    # credentials = ServiceAccountCredentials.from_json_keyfile_name('backend/dolphin/google-credentials.json', scopes)
    # gc = gspread.authorize(credentials)
    s = OlympTradeAPI()
    date_time = datetime.now()
    date_str = date_time.strftime("%d/%m/%Y, %H:%M:%S")
    get_report, get_results = s.get_profit_lose_analysis(date_time)
    #backend/dolphin/common/templates/rendering_table.html
    return render(request, 'rendering_table.html', {'forex_data': get_report, 'get_results': get_results})

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
    logger.info(last_row_value)
    logger.info(type(last_row_value))
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
        logger.info(f'{i} import Starting..!!!!')
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
        logger.info(f'{i} imported Successfully..!!!!')
    return True