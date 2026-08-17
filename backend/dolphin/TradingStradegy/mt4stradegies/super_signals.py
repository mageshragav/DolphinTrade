import pandas as pd
import numpy as np
from datetime import timedelta

class SuperSignalV2Generator:
    def __init__(self, df: pd.DataFrame, file_path=None):
        self.df = df
        self.parameters = {
                'dist': 24,
                'SignalGap': 4,
                'SoundON': True,
                'EmailON': False
            }
        self.initialize_buffers_and_flags()

    def initialize_buffers_and_flags(self):
        self.df['SuperSignalV2'] = 0
        self.flagval1 = 0
        self.flagval2 = 0

    @staticmethod
    def highest(data, length):
        return data.rolling(window=length, min_periods=1).max()

    @staticmethod
    def lowest(data, length):
        return data.rolling(window=length, min_periods=1).min()

    def calculate_signals(self):
        dist = self.parameters['dist']
        for i in range(dist, len(self.df)):
            hhb = self.highest(self.df['high'].iloc[i - dist + 1:i + 1], dist).iloc[-1]
            llb = self.lowest(self.df['low'].iloc[i - dist + 1:i + 1], dist).iloc[-1]

            # Buy signal
            if self.df['high'].iloc[i] == hhb:
                self.df.at[self.df.index[i], 'SuperSignalV2'] = 2

            # Sell signal
            if self.df['low'].iloc[i] == llb:
                self.df.at[self.df.index[i], 'SuperSignalV2'] = 1
        return self.df

    def save_results(self, output_file):
        self.df['UTC'] = pd.to_datetime(self.df['datetime']) + timedelta(hours=5)
        self.df['GMT'] = self.df['UTC'] + timedelta(hours=2)
        self.df.to_csv(output_file, index=False)

    def run(self, output_file=None) -> pd.DataFrame:
        return self.calculate_signals()