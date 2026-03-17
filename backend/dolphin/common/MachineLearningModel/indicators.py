from ta import momentum,volatility,volume,trend
from ta import add_all_ta_features
import pandas as pd




class IndicatorsData:

    def __init__(self,dataframe: pd.DataFrame) -> pd.DataFrame:
        self.dataframe = dataframe
        self.high,self.low = self.dataframe['high'],self.dataframe['low']
        self.open,self.close = self.dataframe['open'],self.dataframe['close']
        self.volume = self.dataframe['volume']
        return_data = {"RSI":self.RSI_value(),
                       "MCAD": self.MCAD_value(),
                       "CCI": self.CCI_value(),
                    #    "ALI": self.ALLIGATOR_value(),
                       "W%R": self.WR_value(),
                       "ADX": self.ADX_value(),
                       "STOCH": self.STOCH_value(),
                       "AO": self.AO_value()}
        indicator_data = pd.DataFrame(return_data)
        new_data = pd.concat([self.dataframe,indicator_data],axis=1)
        # return_data = add_all_ta_features(dataframe,open=self.open,close=self.close,high=self.high,low=self.low,
        #                                   volume=self.volume)
        return new_data


    def RSI_value(self):
        rsi = momentum.rsi(self.dataframe['close'],window=14)
        return rsi

    def CCI_value(self):
        cci = trend.cci(high=self.high,low=self.low,close=self.close)

    def MCAD_value(self):
        mcad = trend.macd(close=self.close)
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