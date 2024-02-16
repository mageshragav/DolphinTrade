import pandas as pd
# from ta_py import ta
import numpy as np
from ta import add_all_ta_features,momentum
from ta import momentum,volatility,volume,trend
from ta import add_all_ta_features
import pandas as pd
class IndicatorsData:

    def __init__(self,dataframe: pd.DataFrame) -> pd.DataFrame:
        self.dataframe = dataframe
        self.high,self.low = 'high','low'
        self.open,self.close = 'open','close'
        self.volume = 'volume'
        self.indicator_list = ['datetime','symbol','high','low','open','close','volume','trend_macd','trend_macd_signal','trend_adx','trend_cci','momentum_rsi',
                               'momentum_stoch', 'momentum_stoch_signal', 'momentum_uo','momentum_wr', 'momentum_ao']
        self.new_data = add_all_ta_features(self.dataframe,open=self.open,close=self.close,high=self.high,low=self.low,
                                          volume=self.volume,fillna=True)
        self.filter_data = self.new_data[self.indicator_list]
        self.win_or_lose(self.filter_data)
    
    def convert_to_csv(self):
        self.filter_data.to_csv('common/MachineLearningModel/output/output_1.csv')

    def win_or_lose(self,df: pd.DataFrame):
        df['Prediction'] = df.apply(lambda x: 'SELL' if x['open'] > x['close'] else 'NEUTRAL' if x['open'] == x['close'] else 'BUY',axis=1)

    def RSI_value(self):
        rsi = momentum.rsi(self.dataframe['close'],window=14)
        return rsi

    def CCI_value(self):
        cci = trend.cci(high=self.high,low=self.low,close=self.close)

    def MCAD_value(self):
        mcad = trend.macd(close=self.close)
        return mcad
    
    def MCAD_signal_value(self):
        mcad = trend.macd_signal(close=self.close)
        return mcad

    # def ALLIGATOR_value(self):
    #     pass

    def WR_value(self):
        wr = momentum.williams_r(high=self.high,low=self.low,close=self.close)
        return wr

    def ADX_value(self):
        adx = trend.adx(high=self.high,low=self.low,close=self.close)
        return adx

    def STOCH_value(self):
        stoch = momentum.stoch_signal(high=self.high,low=self.low,close=self.close)
        return stoch

    def AO_value(self):
        oscillator = momentum.awesome_oscillator(high=self.high,low=self.low)
        return oscillator

data = pd.read_csv('EURJPY_5_Min.csv')
i = IndicatorsData(data)
i.convert_to_csv()
print('done')


# print(new_df.tail()['momentum_rsi'])
# data.sort_values(by='datetime',inplace=True,ascending=False)
# data[['RSI','MCAD','W%R','CCI','ATR']] = None
# # print(list(data.index))
# rsi = list()
# for i in range(len(data),0,-1):
#     length = 14; # default = 14
#     # print(f"{i} {i-14}")
#     # print(list(data[i:i-14]['close']))
#     closing_series = data[i-14:i]['close'].sort_index(ascending=True)
#     r = momentum.rsi(closing_series, length)
#     try:
#         rsi.append(r.dropna().iloc[0])
#     except:
#         rsi.append(np.nan)
# data['RSI']=rsi
# print(data.head())
# rsi = list()
# for i in list(data.index):
#     print(i)
#     length = 14; # default = 14
#     print(f"{i} {14+i}")
#     # r = momentum.rsi(data[i:14+i]['close'], length)
#     # print(r.to_list())
#     break5=