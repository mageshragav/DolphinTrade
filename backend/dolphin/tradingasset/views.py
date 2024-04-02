import pickle
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
from ta.trend import macd,cci,adx,macd_signal,adx_pos,adx_neg
from ta.momentum import rsi,stochrsi_d,stochrsi_k,stochrsi
import numpy as np
# Create your views here.
# value = list()
class OlympTradeTrigger:
    def __init__(self) -> None:
        # symbols,screener,exchange,interval
        balance_key = 'demo' #real
        self.olymp_client = OlympTradeClient(group='demo')
        self.balance = self.olymp_client.balance
        self.ml_model = pickle.load(open('backend/dolphin/xgbclassifier.sav','rb'))
        # self.ml_model = pickle.load(open('backend/dolphin/combineclassifier.sav','rb'))
        # self.ml_model_15 = pickle.load(open('backend/dolphin/xgbclassifier_15.sav','rb'))
        self.s = main.TvDatafeed('mageshragav1@gmail.com','Magesh1@')
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

    @staticmethod
    def calculate(pd: pd.DataFrame) -> pd.DataFrame:
        pdrsi = rsi(pd['close'],14)
        # rsi.dropna(axis=0,inplace=True)
        pdcci = cci(pd['high'],pd['low'],pd['close'],14)
        # cci.dropna(axis=0,inplace=True)
        pdadx = adx(pd['high'],pd['low'],pd['close'])
        pdadx_pos = adx_pos(pd['high'],pd['low'],pd['low']) 
        pdadx_neg = adx_neg(pd['high'],pd['low'],pd['low'])
        # adx.dropna(axis=0,inplace=True)
        pdmacd = macd(pd['close'])
        # macd.dropna(axis=0,inplace=True)
        pdmacd_signal = macd_signal(pd['close'])
        # macd_signal.dropna(axis=0,inplace=True)
        pdstochrsi_d = stochrsi_d(pd['close'])
        pdstochrsi_k = stochrsi_k(pd['close'])
        pdstochrsi = stochrsi(pd['close'])
        # stochrsi.dropna(axis=0,inplace=True)
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
        return pd2
    

    def start_trading(self, symbols='EURUSD'):
        import random
        symbols = random.choice(ALL_SYMBOLS)
        print(symbols)
        response_data = self.s.get_hist(symbol=symbols,exchange='FX',interval=main.Interval.in_5_minute,n_bars=300,extended_session=False)
        result_pd = OlympTradeTrigger.calculate(response_data)
        adx_condition = ((result_pd['adx'] > 25.00) & (result_pd['adx'] < 30.00))
        result_pd['RSI_1'] = np.where(result_pd['rsi'] < 30, 1, np.where(result_pd['rsi'] > 70, 2, 0))
        result_pd['ADX_1'] = np.where((result_pd['adx'] > 25.00) & (result_pd['adx_pos'] < result_pd['adx_neg']), 1, np.where((result_pd['adx'] > 25.00) & (result_pd['adx_pos'] > result_pd['adx_neg']), 2, 0))
        conditions_3 = (result_pd['stochrsi'] > 0.75) & (result_pd['stochrsi_k'] < result_pd['stochrsi_d'])
        conditions_4 = (result_pd['stochrsi'] < 0.25) & (result_pd['stochrsi_k'] > result_pd['stochrsi_d'])
        result_pd['STOCH.RSI'] = np.where(conditions_3, 2, np.where(conditions_4, 1, 0))
        result_pd['ADX_1'] = np.where(adx_condition & (result_pd['adx_pos'] < result_pd['adx_neg']), 1, np.where(adx_condition & (result_pd['adx_pos'] > result_pd['adx_neg']), 2, 0))
        conditions_3 = (result_pd['stochrsi'] > 0.75) & (result_pd['stochrsi_k'] < result_pd['stochrsi_d'])
        conditions_4 = (result_pd['stochrsi'] < 0.25) & (result_pd['stochrsi_k'] > result_pd['stochrsi_d'])
        result_pd['STOCH.RSI'] = np.where(conditions_3, 2, np.where(conditions_4, 1, 0))
        # result_pd['RSI_1'] = result_pd['RSI_1'] = np.where(result_pd['rsi'] < 30, 1, np.where(result_pd['rsi'] > 70, 2, 0))
        result_pd.dropna(inplace=True)
        result_pd.reset_index()
        print(result_pd.iloc[-1])
        data_1 = result_pd.iloc[-1,5:].to_dict()
        data_1 = pd.DataFrame({key: [value] for key, value in data_1.items()})
        print(data_1)
        ml_output = self.ml_model.predict(data_1)
        # ml_output = self.ml_model_15.predict(data_1)
        if ml_output[0] == 1:
            msg = f'Recommended for next 5 min in {symbols} was BUY'
            print(msg)
            response = send_telegram_message.apply_async(args=(IMAGE_GREEN, msg))
            response_data = self.olymp_client.get_bet('up',symbols,amount='1',duration='300')
        elif ml_output[0] == 2:
            msg = f'Recommended for next 5 min in {symbols} was SELL'
            print(msg)
            response = send_telegram_message.apply_async(args=(IMAGE_RED, msg))
            response_data = self.olymp_client.get_bet('down',symbols,amount='1',duration='300')
        else:
            print('neutral')


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
            # recommend = self.trading_signal.personal_recommendation(data=summary,oscillator=oscillator, indicator=indicators,mv=mov_avg)
            # msg = self.message_generator(signal_value=summary,asset=symbols,indicators=indicators,moving_avg=mov_avg)
            # # response = send_telegram_message.apply_async(args=('', msg))
            # if recommend['BUY']:
            #     response_data = self.olymp_client.get_bet('up',symbols,amount='1',duration='300')
            #     response = send_telegram_message.apply_async(args=(IMAGE_GREEN, msg))
            #     data = {'personal': 'BUY','direction': 'up','asset': symbols, 'amount': '1', 'duration': '300'}
            #     self.db_entry(summary=summary,mov_avg=mov_avg,indicators=indicators,data=data, oscillator=oscillator)
            #     # print(response_data)
            #     print(f"================TRADING SUCCESS WITH BUY {symbols}=======================")
            #     print(symbols,summary,oscillator,indicators,mov_avg)
            #     print('================TRADING SUCCESS WITH BUY END=======================')
            # elif recommend['SELL']:
            #     response_data = self.olymp_client.get_bet('down',symbols,amount='1',duration='300')
            #     response = send_telegram_message.apply_async(args=(IMAGE_RED, msg))
            #     data = {'personal': 'SELL','direction': 'down','asset': symbols, 'amount': '1', 'duration': '300'}
            #     self.db_entry(summary=summary,mov_avg=mov_avg,indicators=indicators,data=data, oscillator=oscillator)
            #     print(f"================TRADING SUCCESS WITH SELL {symbols}=======================")
            #     print(symbols,summary,oscillator,indicators,mov_avg)
            #     print('================TRADING SUCCESS WITH SELL END=======================')
            #     # print(response_data)
            # summary['RSI'] = indicators['RSI']
            # summary['MACD'] = oscillator['COMPUTE']['MACD']
            # oscillator.update(indicators)
            # mv_ag = mov_avg['COMPUTE']
            # oscillator.update(mv_ag)
            # summary['TOTAL'] = json.dumps(oscillator)
                
            # return summary, recommend
        except Exception as e:
            print(e.args)

    def multi_trigger(self):
        try:
            value = list()
            current_time = timezone.now().astimezone(pytz.timezone('America/New_York'))
            for timeing, assets in TIME_SYMBOL_MAPPING.items():
                # if timeing[0] <= current_time.replace(tzinfo=None) <= timeing[1]:
                #     for asset in assets:
                #         five_min = timezone.now() - timedelta(minutes=5)
                #         if not OlympTrade.objects.filter(asset=asset, created_at__range=[five_min,timezone.now()]).exists():
                recommend = self.single_trigger(symbols='EURUSD')
                return recommend
                    #         if recommend['SELL'] or recommend['BUY']:
                    #             summary['asset'] = asset
                    #             summary['personal'] = recommend
                    #             summary['date_time'] = timezone.now().strftime("%d/%m/%Y %H:%M:%S")
                    #             value.append(summary)
                    # self.olymp_client.disconnect()
            return value
            # else:
            #     for asset in EUR_SYMBOLS:
            #         summary, recommend = self.single_trigger(symbols=asset)
            #         summary['asset'] = asset
            #         summary['personal'] = recommend
            #         value.append(summary)
        except Exception as e:
            print(e.args)

    def data_creation(self):
        df = pd.DataFrame()
        for symbol in USD_SYMBOLS:
            mov = dict()
            five_min = Interval.INTERVAL_5_MINUTES
            self.trading_signal = TradingViewApi(symbols=symbol,screener=SCREENER,exchange=EXCHANGE,interval=five_min)
            signal = self.trading_signal.signal
            oscillator = self.trading_signal.get_oscillators(signal)
            print(oscillator)
            mov_avg = self.trading_signal.get_moving_avg(signal=signal)
            indicators = self.trading_signal.get_indicators(signal=signal)
            oscillator['COMPUTE']['SYMBOL'] = symbol
            oscillator['COMPUTE']['OPEN'] = indicators['open']
            oscillator['COMPUTE']['CLOSE'] = indicators['close']
            oscillator['COMPUTE']['DATA/TIME'] = datetime.strftime(datetime.now(),'%Y-%m-%d %H:%M:%S')
            print(mov_avg)
            mov = {"Ichimoku": mov_avg['COMPUTE']['Ichimoku'], "VWMA": mov_avg['COMPUTE']['VWMA'], "HullMA": mov_avg['COMPUTE']['HullMA']}
            oscillator['COMPUTE'].update(mov)
            self.olymp_client.get_bet('up',symbol,amount='1',duration='300')
            if len(df) == 0:
                df = pd.DataFrame([oscillator['COMPUTE']])
            else:
                df.loc[len(df)] = oscillator['COMPUTE']
        self.olymp_client.disconnect()
        put_excel(df)
        return 'success'



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