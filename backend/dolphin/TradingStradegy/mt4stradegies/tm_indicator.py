import pandas as pd
from datetime import timedelta
import numpy as np

# Stradegy No. 2 TMA Indicator 
# Description :
    # Triangular moving average (TMA) indicator is a modified version of a moving average. Similarly to a common MA, triangular moving average
    # is displayed as a simple line on charts. Triangular moving average is calculated as double-smoothed moving average of the price for the 
    # past N periods. This makes it really smooth and wave-like

class TMIndicator:

    def __init__(self,df: pd.DataFrame) -> None:
        self.df = df.copy()
        # Define the parameters
        self.half_length = 10
        self.price_column = 'close'
        self.bands_deviations = 2.4
        self.koeff = 0.0001
        self.interpolate = True
        # Initialize buffers
        self.tm_buffer = np.zeros(len(self.df))
        self.up_buffer = np.zeros(len(self.df))
        self.dn_buffer = np.zeros(len(self.df))
        self.wu_buffer = np.zeros(len(self.df))
        self.wd_buffer = np.zeros(len(self.df))
        self.up_arrow = np.full(len(self.df), np.nan)
        self.dn_arrow = np.full(len(self.df), np.nan)

    # Calculate the TMA and bands
    def calculate_tma(self, half_length, price_column, bands_deviations, koeff):
        full_length = 2.0 * half_length + 1.0
        
        for i in range(len(self.df)):
            sum_val = (half_length + 1) * self.df[price_column].iloc[i]
            sumw = half_length + 1
            for j in range(1, half_length + 1):
                if i - j >= 0:
                    sum_val += (half_length - j + 1) * self.df[price_column].iloc[i - j]
                    sumw += (half_length - j + 1)
            
            self.tm_buffer[i] = sum_val / sumw
            
            if i >= half_length:
                diff = self.df[price_column].iloc[i] - self.tm_buffer[i]
                if i == half_length:
                    self.wu_buffer[i] = np.power(diff, 2) if diff >= 0 else 0
                    self.wd_buffer[i] = np.power(diff, 2) if diff < 0 else 0
                else:
                    self.wu_buffer[i] = (self.wu_buffer[i-1] * (full_length - 1) + np.power(diff, 2)) / full_length if diff >= 0 else self.wu_buffer[i-1] * (full_length - 1) / full_length
                    self.wd_buffer[i] = (self.wd_buffer[i-1] * (full_length - 1) + np.power(diff, 2)) / full_length if diff < 0 else self.wd_buffer[i-1] * (full_length - 1) / full_length

                self.up_buffer[i] = self.tm_buffer[i] + bands_deviations * np.sqrt(self.wu_buffer[i])
                self.dn_buffer[i] = self.tm_buffer[i] - bands_deviations * np.sqrt(self.wd_buffer[i])
        
        return self.tm_buffer, self.up_buffer, self.dn_buffer

    def calculate(self):
        return self.calculate_tma(self.half_length, self.price_column, self.bands_deviations, self.koeff)
    def run(self) -> pd.DataFrame:
        # Generate arrows (current-bar only, no lookahead)
        self.tm_buffer, self.up_buffer, self.dn_buffer = self.calculate()
        for i in range(1, len(self.df)):
            if self.df['high'].iloc[i] > self.up_buffer[i] and self.df['close'].iloc[i] > self.df['open'].iloc[i] and self.df['close'].iloc[i - 1] < self.df['open'].iloc[i - 1]:
                self.up_arrow[i] = self.df['high'].iloc[i] + self.df['close'].rolling(window=20).mean().iloc[i] + self.koeff
            if self.df['low'].iloc[i] < self.dn_buffer[i] and self.df['close'].iloc[i] < self.df['open'].iloc[i] and self.df['close'].iloc[i - 1] > self.df['open'].iloc[i - 1]:
                self.dn_arrow[i] = self.df['low'].iloc[i] - self.df['close'].rolling(window=20).mean().iloc[i] - self.koeff
        # return self.df
        decimal_length = len(str(self.df['open'].iloc[0]).split('.')[1])
        
        # Use .loc to avoid the SettingWithCopyWarning
        self.df.loc[:, 'tm_buffer'] = np.round(self.tm_buffer, decimal_length)
        self.df.loc[:, 'up_buffer'] = np.round(self.up_buffer, decimal_length)
        self.df.loc[:, 'dn_buffer'] = np.round(self.dn_buffer, decimal_length)
        self.df.loc[:, 'up_arrow'] = np.round(self.up_arrow, decimal_length)
        self.df.loc[:, 'dn_arrow'] = np.round(self.dn_arrow, decimal_length)
        self.df.loc[:,'TMSignal'] = 0
        # Vectorized computation for SELL_TM and BUY_TM
        self.df.loc[
            (self.df[['open', 'close']].min(axis=1) <= self.df['up_buffer']) & 
            (self.df['up_buffer'] <= self.df[['open', 'close']].max(axis=1)), 
            'TMSignal'
        ] = 2

        # Set TMSignal to 1 if dn_buffer is within the range of open and close
        self.df.loc[
            (self.df[['open', 'close']].min(axis=1) <= self.df['dn_buffer']) & 
            (self.df['dn_buffer'] <= self.df[['open', 'close']].max(axis=1)), 
            'TMSignal'
        ] = 1
        return self.df