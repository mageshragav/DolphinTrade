import pandas as pd
import numpy as np
import ta
from datetime import timedelta

class SuperArrowSignalGenerator:
    def __init__(self, df: pd.DataFrame,file_path=None):
        self.df = df.reset_index(drop=True)
        self.parameters = {
            'FasterMovingAverage': 5,
            'SlowerMovingAverage': 12,
            'RSIPeriod': 12,
            'MagicFilterPeriod': 1,
            'BollingerbandsPeriod': 10,
            'BollingerbandsShift': 0,
            'BollingerbandsDeviation': 0.5,
            'BullsPowerPeriod': 50,
            'BearsPowerPeriod': 50,
            'Utstup': 10,
            'Alerts': True
        }
        self.initialize_conditions()

    def initialize_conditions(self):
        self.Gi_132 = False
        self.Gi_136 = False
        self.Gi_140 = False
        self.Gi_144 = False
        self.Gi_148 = False
        self.Gi_152 = False
        self.Gi_156 = False
        self.Gi_160 = False
        self.Gi_164 = False
        self.Gi_168 = False
        self.Gi_172 = 0
        self.Gi_176 = False
        self.Gi_180 = False

    def calculate_indicators(self):
        params = self.parameters
        self.df['ema_fast'] = ta.trend.ema_indicator(self.df['close'], window=params['FasterMovingAverage'])
        self.df['ema_slow'] = ta.trend.ema_indicator(self.df['close'], window=params['SlowerMovingAverage'])
        self.df['rsi'] = ta.momentum.rsi(self.df['close'], window=params['RSIPeriod'])
        self.df['bulls_power'] = self.df['high'] - ta.trend.ema_indicator(self.df['close'], window=params['BullsPowerPeriod'])
        self.df['bears_power'] = self.df['low'] - ta.trend.ema_indicator(self.df['close'], window=params['BearsPowerPeriod'])
        bb = ta.volatility.BollingerBands(self.df['close'], window=params['BollingerbandsPeriod'], window_dev=params['BollingerbandsDeviation'])
        self.df['bb_upper'] = bb.bollinger_hband()
        self.df['bb_lower'] = bb.bollinger_lband()

    def apply_strategy(self):
        self.df['SuperArrowSignal'] = 0
        for i in range(len(self.df)-1, 1, -1):
            if i < 10:
                continue  # Skip initial periods where sufficient data isn't available

            Ld_140 = np.sum(np.abs(self.df['high'][i:i + 10] - self.df['low'][i:i + 10]))
            Ld_132 = Ld_140 / 10.0
            Ld_124 = 100 - 100.0 * ((Ld_132 - 0.0) / 10.0)

            if Ld_124 >= 0.0:
                self.Gi_148 = True
                self.Gi_168 = False
            else:
                self.Gi_148 = False
                self.Gi_168 = True

            if self.df['close'][i] > self.df['bb_upper'][i] and self.df['close'][i - 1] >= self.df['bb_upper'][i - 1]:
                self.Gi_144 = False
                self.Gi_164 = True

            if self.df['close'][i] < self.df['bb_lower'][i] and self.df['close'][i - 1] <= self.df['bb_lower'][i - 1]:
                self.Gi_144 = True
                self.Gi_164 = False

            if self.df['bulls_power'][i] > 0.0 and self.df['bulls_power'][i - 1] > self.df['bulls_power'][i]:
                self.Gi_140 = False
                self.Gi_160 = True

            if self.df['bears_power'][i] < 0.0 and self.df['bears_power'][i - 1] < self.df['bears_power'][i]:
                self.Gi_140 = True
                self.Gi_160 = False

            if self.df['rsi'][i] > 50.0 and self.df['rsi'][i - 1] < 50.0:
                self.Gi_136 = True
                self.Gi_156 = False

            if self.df['rsi'][i] < 50.0 and self.df['rsi'][i - 1] > 50.0:
                self.Gi_136 = False
                self.Gi_156 = True

            if self.df['ema_fast'][i] > self.df['ema_slow'][i] and self.df['ema_fast'][i - 1] < self.df['ema_slow'][i - 1]:
                self.Gi_132 = True
                self.Gi_152 = False

            if self.df['ema_fast'][i] < self.df['ema_slow'][i] and self.df['ema_fast'][i - 1] > self.df['ema_slow'][i - 1]:
                self.Gi_132 = False
                self.Gi_152 = True

            if (self.Gi_132 and self.Gi_136 and self.Gi_144 and self.Gi_140 and self.Gi_148 and self.Gi_172 != 1):
                self.df.at[i, 'SuperArrowSignal'] = 1
                self.Gi_172 = 1

            elif (self.Gi_152 and self.Gi_156 and self.Gi_164 and self.Gi_160 and not self.Gi_168 and self.Gi_172 != 2):
                self.df.at[i, 'SuperArrowSignal'] = 2
                self.Gi_172 = 2
        return self.df

    def save_results(self, output_file):
        self.df['UTC'] = pd.to_datetime(self.df['datetime']) + timedelta(hours=5)
        self.df['GMT'] = self.df['UTC'] + timedelta(hours=2)
        self.df.to_csv(output_file, index=False)

    def run(self, output_file=None) -> pd.DataFrame:
        self.calculate_indicators()
        return self.apply_strategy()