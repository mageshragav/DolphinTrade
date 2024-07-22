import pandas as pd
import numpy as np
import ta.volatility
import ta.momentum
import ta.volume
import ta.trend
from datetime import timedelta,datetime
class IINWMARROWSSignalPredictor:
    def __init__(self, df):
        """
        Initialize the MovAvg class with a DataFrame.
        :param df: pandas DataFrame with columns 'close', 'open', 'high', and 'low'.
        """
        self.df = df

    def calculate_ma(self, series, period, mode):
        """
        Calculate the moving average based on the specified mode.
        :param series: pandas Series to calculate the moving average on.
        :param period: int, the window period for the moving average.
        :param mode: int, the mode of moving average (0: SMA, 1: EMA, 2: SMMA, 3: LWMA).
        :return: pandas Series with the moving average.
        """
        if mode == 0:  # Simple Moving Average (SMA)
            return series.rolling(window=period).mean()
        elif mode == 1:  # Exponential Moving Average (EMA)
            return series.ewm(span=period, adjust=False).mean()
        elif mode == 2:  # Simple Modified Moving Average (SMMA)
            return series.ewm(alpha=1.0 / period).mean()
        elif mode == 3:  # Linear Weighted Moving Average (LWMA)
            weights = np.arange(1, period + 1)
            return series.rolling(period).apply(lambda prices: np.dot(prices, weights) / weights.sum(), raw=True)
        else:
            raise ValueError("Invalid mode for moving average")

    def run(self):
        """
        Main loop to calculate moving averages and detect cross signals.
        :return: pandas DataFrame with 'CrossDown', 'CrossUp', 'FasterMA', and 'SlowerMA' columns.
        """
        # Parameters
        faster_mode = 3  # LWMA
        faster_ma_period = 3
        slower_mode = 3  # LWMA
        slower_ma_period = 3

        # Calculate moving averages
        self.df['FasterMA'] = self.calculate_ma(self.df['close'], faster_ma_period, faster_mode)
        self.df['SlowerMA'] = self.calculate_ma(self.df['open'], slower_ma_period, slower_mode)

        # Calculate range and average range
        self.df['Range'] = self.df['high'] - self.df['low']
        self.df['AvgRange'] = self.df['Range'].rolling(window=10).mean()

        # Initialize columns for cross signals
        self.df.loc[:,'ImmArrow'] = 0

        # Detect cross signals
        crosses_up = (
            (self.df['FasterMA'] > self.df['SlowerMA']) &
            (self.df['FasterMA'].shift(1) < self.df['SlowerMA'].shift(1)) &
            (self.df['FasterMA'] > self.df['FasterMA'].shift(1))
        )
        crosses_down = (
            (self.df['FasterMA'] < self.df['SlowerMA']) &
            (self.df['FasterMA'].shift(1) > self.df['SlowerMA'].shift(1)) &
            (self.df['FasterMA'] < self.df['FasterMA'].shift(1))
        )

        self.df.loc[crosses_up, 'ImmArrow'] = 1
        self.df.loc[crosses_down, 'ImmArrow'] = 2
        self.df.to_csv('/tmp/immarrow.csv')
        # return self.df[['ImmArrow']]
        return self.df

