import pandas as pd
import numpy as np
from datetime import timedelta
import ta.volatility
import ta.momentum
import ta.volume
import ta.trend

class SuperV3SignalPredictor:
    def __init__(self, data=None, file_path=None, output_file=None):
        self.file_path = file_path
        self.output_file = output_file
        self.data = data
        self.setup_parameters()

    def load_data(self):
        return pd.read_csv(self.file_path)

    def setup_parameters(self):
        # Define parameters
        self.dist1 = 14
        self.dist2 = 21

    def calculate_indicators(self):
        df = self.data
        
        # Calculate highest and lowest values over dist1 and dist2 periods
        df['hhb1'] = df['high'].rolling(window=self.dist1, center=True).max()
        df['llb1'] = df['low'].rolling(window=self.dist1, center=True).min()
        df['hhb'] = df['high'].rolling(window=self.dist2, center=True).max()
        df['llb'] = df['low'].rolling(window=self.dist2, center=True).min()
        
        # Calculate ATR
        df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=50)

    def generate_signals(self):
        df = self.data

        # Initialize b1, b2, b3, b4
        df['b1'] = np.nan
        df['b2'] = np.nan
        df['b3'] = np.nan
        df['b4'] = np.nan

        # Fill b1, b2, b3, b4 based on conditions
        df.loc[df['high'] == df['hhb'], 'b1'] = df['high'] + df['atr']
        df.loc[df['low'] == df['llb'], 'b2'] = df['low'] - df['atr']
        df.loc[df['high'] == df['hhb1'], 'b3'] = df['high'] + df['atr'] / 2
        df.loc[df['low'] == df['llb1'], 'b4'] = df['low'] - df['atr'] / 2
        df['SuperSignalV3'] = 0
        # Generate signals
        conditions = [
            (df['b1'].notna() & df['b3'].notna(), 2),
            (df['b1'].notna() & df['b3'].isna(), 2),
           # (df['b1'].isna() & df['b3'].notna(), -2),
            (df['b2'].notna() & df['b4'].notna(), 1),
            (df['b2'].notna() & df['b4'].isna(), 1),
           # (df['b2'].isna() & df['b4'].notna(), -1)
        ]

        # Apply conditions to generate signals
        for condition, signal in conditions:
            df.loc[condition, 'SuperSignalV3'] = signal
        return df

    def adjust_timezones(self):
        df = self.data
        df['UTC'] = pd.to_datetime(df['datetime']) + timedelta(hours=5)
        df['GMT'] = df['UTC'] + timedelta(hours=2)

    def save_output(self):
        self.data.to_csv(self.output_file, index=False)

    def run(self) -> pd.DataFrame:
        self.calculate_indicators()
        data = self.generate_signals()
        # data.to_csv('/tmp/supersignalv3.csv')
        # return data[['SuperSignalV3']]
        return data
        # self.adjust_timezones()
        # self.save_output()
