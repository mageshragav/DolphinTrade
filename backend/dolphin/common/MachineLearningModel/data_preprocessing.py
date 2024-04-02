import numpy as np
import requests
from django.conf import settings
import pandas as pd
from ta import momentum,volatility,trend,others
from MachineLearningModel.indicators import IndicatorsData

class Recommendation:
    buy = 2
    sell = 3
    neutral = 1

class DataPreProcessing:
    
    def __init__(self) -> pd.DataFrame:
        self.Df_data = self.get_data('EURUSD',5)
        self.add_Indicators_column()
        output_df = IndicatorsData()
        output_df.to_csv('output/new_ouput.csv')
        return output_df

    
    def get_data(self,asset: str,timeframe: int) -> pd.DataFrame:
        data_pd = pd.read_csv(f'backend/dolphin/Data/{asset}_{timeframe}_MIN.csv')
        return data_pd
    
    def add_Indicators_column(self, columns: list=[]) -> None:
        if columns is None:
            columns = ['RSI','MCAD','W%R','CCI', 'ADX','STOCH','AO']
        self.Df_data[columns] = None

    def RSI(rsi):
        """Compute Relative Strength Index

        Args:
            rsi (float): RSI value

        Returns:
            string: "BUY", "SELL", or "NEUTRAL"
        """
        if (rsi < 30):
            return Recommendation.buy
        elif (rsi > 70):
            return Recommendation.sell
        else:
            return Recommendation.neutral

    def Stoch(k, d):
        """Compute Stochastic

        Args:
            k (float): Stoch.K value
            d (float): Stoch.D value

        Returns:
            string: "BUY", "SELL", or "NEUTRAL"
        """
        if (k < 20 and d < 20 and k > d):
            return Recommendation.buy
        elif (k > 80 and d > 80 and k < d):
            return Recommendation.sell
        else:
            return Recommendation.neutral

    def CCI20(cci20,rsi):
        """Compute Commodity Channel Index 20

        Args:
            cci20 (float): CCI20 value
            cci201 ([type]): CCI20[1] value

        Returns:
            string: "BUY", "SELL", or "NEUTRAL"
        """
        rsi = DataPreProcessing.RSI(rsi)
        if (cci20 < -100) and (rsi == 2):
            return Recommendation.buy
        elif (cci20 > 100) and (rsi == 1):
            return Recommendation.sell
        else:
            return Recommendation.neutral

    def ADX(adx, adxpdi, adxndi):
        """Compute Average Directional Index

        Args:
            adx (float): ADX value
            adxpdi (float): ADX+DI value
            adxndi (float): ADX-DI value

        Returns:
            string: "BUY", "SELL", or "NEUTRAL"
        """
        if (adx > 20 and adxpdi > adxndi):
            return Recommendation.buy
        elif (adx > 20 and adxpdi < adxndi):
            return Recommendation.sell
        else:
            return Recommendation.neutral

    def AO(ao,rsi):
        """Compute Awesome Oscillator

        Args:
            ao (float): AO value
            ao1 (float): AO[1] value
            ao2 (float): AO[2] value

        Returns:
            string: "BUY", "SELL", or "NEUTRAL"
        """
        rsi = DataPreProcessing.RSI(rsi)
        if (ao > 0) and rsi == 2:
            return Recommendation.buy
        elif (ao < 0) and rsi == 3:
            return Recommendation.sell
        else:
            return Recommendation.neutral
    
    def UO(uo,rsi):
        """Compute Awesome Oscillator

        Args:
            uo (float): UO value

        Returns:
            string: "BUY", "SELL", or "NEUTRAL"
        """
        rsi = DataPreProcessing.RSI(rsi)
        if (uo > 0) and rsi == 2:
            return Recommendation.buy
        elif (uo < 0) and rsi == 3:
            return Recommendation.sell
        else:
            return Recommendation.neutral
    
    def MACD(macd, signal):
        """Compute Moving Average Convergence/Divergence

        Args:
            macd (float): MACD.macd value
            signal (float): MACD.signal value

        Returns:
            string: "BUY", "SELL", or "NEUTRAL"
        """
        if (macd > signal):
            return Recommendation.buy
        elif (macd < signal):
            return Recommendation.sell
        else:
            return Recommendation.neutral
        
    def WR(wr,rsi):
        rsi = DataPreProcessing.RSI(rsi)
        if wr > -20 and rsi == 3:
            return Recommendation.sell
        elif wr < -80 and rsi == 2:
            return Recommendation.buy
        else:
            return Recommendation.neutral
