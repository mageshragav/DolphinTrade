import pandas as pd
import numpy as np
import ta.volatility
import ta.momentum
import ta.volume
import ta.trend
from datetime import timedelta

# class ExtremeBinarySignalPredictor:
#     def __init__(self, data=None,file_path=None, Gd_228=25.0, Gi_220=17, EnableAlert=True, SoundFilename="alert.wav"):
#         self.file_path = file_path
#         self.Gd_228 = Gd_228
#         self.Gi_220 = Gi_220
#         self.EnableAlert = EnableAlert
#         self.SoundFilename = SoundFilename
#         self.data = data
#         self.data['datetime'] = pd.to_datetime(self.data['datetime'])
#         self.Gd_248 = self.determine_Gd_248()

#     def load_data(self):
#         data = pd.read_csv(self.file_path)
#         data['datetime'] = pd.to_datetime(data['datetime'])
#         return data

#     def determine_Gd_248(self):
#         return 0.0001 if self.data['close'].apply(lambda x: len(str(x).split('.')[1]) < 4).all() else 0.00001

#     def calculate_indicators(self):
#         data = self.data
#         data['ATR'] = ta.volatility.AverageTrueRange(data['high'], data['low'], data['close'], window=5).average_true_range()
#         data['Stochastic'] = ta.momentum.StochasticOscillator(data['high'], data['low'], data['close'], window=20, smooth_window=12).stoch()
#         data['CCI'] = ta.trend.CCIIndicator(data['high'], data['low'], data['close'], window=80).cci()
#         data['Momentum_60'] = ta.momentum.ROCIndicator(data['close'], window=60).roc()
#         data['Momentum_4'] = ta.momentum.ROCIndicator(data['close'], window=4).roc()
#         data['WPR'] = ta.momentum.WilliamsRIndicator(data['high'], data['low'], data['close'], lbp=14).williams_r()
#         data['Force'] = ta.volume.ForceIndexIndicator(data['close'], data['volume'], window=13).force_index()
#         bb = ta.volatility.BollingerBands(data['close'], window=20, window_dev=2)
#         data['Bollinger_Upper'] = bb.bollinger_hband()
#         data['Bollinger_Lower'] = bb.bollinger_lband()
#         data['MA_High'] = ta.trend.EMAIndicator(data['high'], window=1).ema_indicator()
#         data['MA_Median'] = ta.trend.EMAIndicator((data['high'] + data['low']) / 2, window=1).ema_indicator()
#         data['MA_Low'] = ta.trend.EMAIndicator(data['low'], window=1).ema_indicator()

#     def determine_market_condition(self, stochastic_value):
#         if 75.0 >= stochastic_value >= 25.0:
#             return "SAFE TRADE"
#         elif 88.0 >= stochastic_value > 75.0 or 25.0 > stochastic_value >= 12.0:
#             return "S/R AREA"
#         elif stochastic_value > 88.0 or stochastic_value < 12.0:
#             return "HIGH RISK!"
#         else:
#             return ""

#     def apply_market_conditions(self):
#         self.data['Market_Condition'] = self.data['Stochastic'].apply(self.determine_market_condition)

#     def generate_signals(self):
#         data = self.data
#         data.loc[:,'ExtremeBinary'] = 0

#         for i in range(10, len(data)):
#             G_high_324 = data['high'][i-10:i].max()
#             G_low_332 = data['low'][i-10:i].min()
#             Gd_316 = sum((10 - j) * (data['high'][i-j] - data['low'][i-j]) for j in range(10)) / 55.0

#             if data['close'][i] > G_high_324 - (G_high_324 - G_low_332) * self.Gi_220 / 100.0:
#                 data.at[i, 'ExtremeBinary'] = 1
#             elif data['close'][i] < G_low_332 + (G_high_324 - G_low_332) * self.Gi_220 / 100.0:
#                 data.at[i, 'ExtremeBinary'] = 2
#         return data

#     def adjust_timezones(self):
#         self.data['UTC'] = pd.to_datetime(self.data['datetime']) + timedelta(hours=5)
#         self.data['GMT'] = self.data['UTC'] + timedelta(hours=2)

#     def save_output(self, output_file):
#         self.data.to_csv(output_file, index=False)

#     def run(self):
#         self.calculate_indicators()
#         self.apply_market_conditions()
#         data = self.generate_signals()
#         return data[['ExtremeBinary']]
#         # self.adjust_timezones()
#         # self.save_output(output_file)

class ExtremeBinarySignalPredictor:
    def __init__(self,df: pd.DataFrame,df1min: pd.DataFrame, file_path=None, Gd_228=25.0, Gi_220=17, EnableAlert=True, SoundFilename="alert.wav"):
        self.file_path = file_path
        self.Gd_228 = Gd_228
        self.Gi_220 = Gi_220
        self.EnableAlert = EnableAlert
        self.SoundFilename = SoundFilename
        self.data = df
        self.data_1_min = df1min
        self.Gd_248 = self.determine_Gd_248()

    def load_data(self):
        data = pd.read_csv(self.file_path)
        data['datetime'] = pd.to_datetime(data['datetime'])
        return data

    def determine_Gd_248(self):
        return 0.0001 if self.data['close'].apply(lambda x: len(str(x).split('.')[1]) < 4).all() else 0.00001

    def calculate_indicators(self):
        data = self.data
        data_1_min = self.data_1_min
        data['ATR'] = ta.volatility.AverageTrueRange(data['high'], data['low'], data['close'], window=5).average_true_range()
        data['Stochastic'] = ta.momentum.StochasticOscillator(data['high'], data['low'], data['close'], window=20, smooth_window=12).stoch()
        data['CCI'] = ta.trend.CCIIndicator(data_1_min['high'], data_1_min['low'], data_1_min['close'], window=80).cci()
        data['Momentum_60'] = ta.momentum.ROCIndicator(data_1_min['close'], window=60).roc()
        data['Momentum_4'] = ta.momentum.ROCIndicator(data['close'], window=4).roc()
        data['WPR'] = ta.momentum.WilliamsRIndicator(data_1_min['high'], data_1_min['low'], data_1_min['close'], lbp=14).williams_r()
        data['Force'] = ta.volume.ForceIndexIndicator(data['close'], data['volume'], window=13).force_index()
        bb = ta.volatility.BollingerBands(data['close'], window=20, window_dev=2)
        data['Bollinger_Upper'] = bb.bollinger_hband()
        data['Bollinger_Lower'] = bb.bollinger_lband()
        data['MA_High'] = ta.trend.EMAIndicator(data['high'], window=1).ema_indicator()
        data['MA_Median'] = ta.trend.EMAIndicator((data_1_min['high'] + data_1_min['low']) / 2, window=1).ema_indicator()
        data['MA_Low'] = ta.trend.EMAIndicator(data_1_min['low'], window=1).ema_indicator()

    def determine_market_condition(self, stochastic_value):
        if 75.0 >= stochastic_value >= 25.0:
            return "SAFE TRADE"
        elif 88.0 >= stochastic_value > 75.0 or 25.0 > stochastic_value >= 12.0:
            return "S/R AREA"
        elif stochastic_value > 88.0 or stochastic_value < 12.0:
            return "HIGH RISK!"
        else:
            return ""

    def apply_market_conditions(self):
        self.data['Market_Condition'] = self.data['Stochastic'].apply(self.determine_market_condition)
    
    def calculate_extreme_buysell(self,row):
        i = row.name
        if i == 0:  # Skip the first row to avoid out-of-bounds error
            return 0
        if (row['ExtremeBinarySignal'] < row['open'] and 
            self.data.at[i-1, 'Market_Condition'] in ('SAFE TRADE', "S/R AREA") and 
            row['Market_Condition'] != 'HIGH RISK!'):
            return 1
        elif (row['ExtremeBinarySignal'] > row['open'] and 
            self.data.at[i-1, 'Market_Condition'] in ('SAFE TRADE', "S/R AREA") and 
            row['Market_Condition'] != 'HIGH RISK!'):
            return 2
        else:
            return 0

    def generate_signals(self):
        data = self.data
        data['ExtremeBUYSELL'] = 0
        data['ExtremeBinarySignal'] = np.nan

        for i in range(10, len(data)):
            G_high_324 = data['high'][i-10:i].max()
            G_low_332 = data['low'][i-10:i].min()
            Gd_316 = sum((10 - j) * (data['high'][i-j] - data['low'][i-j]) for j in range(10)) / 55.0

            if data['close'][i] > G_high_324 - (G_high_324 - G_low_332) * self.Gi_220 / 100.0:
                data.at[i, 'ExtremeBinarySignal'] = data['high'][i] + Gd_316 / 2.0
            elif data['close'][i] < G_low_332 + (G_high_324 - G_low_332) * self.Gi_220 / 100.0:
                data.at[i, 'ExtremeBinarySignal'] = data['low'][i] - Gd_316 / 2.0
        data['ExtremeBUYSELL'] = data.apply(self.calculate_extreme_buysell, axis=1)
        return data

    def adjust_timezones(self):
        self.data['UTC'] = pd.to_datetime(self.data['datetime']) + timedelta(hours=5)
        self.data['GMT'] = self.data['UTC'] + timedelta(hours=2)

    def save_output(self, output_file):
        self.data.to_csv(output_file, index=False)

    def run(self, output_file=None) -> pd.DataFrame:
        self.calculate_indicators()
        self.apply_market_conditions()
        return self.generate_signals()
        # self.adjust_timezones()
        # self.save_output(output_file)

