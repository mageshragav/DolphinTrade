import numpy as np
import requests
from django.conf import settings
import pandas as pd
from ta import momentum,volatility,trend,others
from MachineLearningModel.indicators import IndicatorsData


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



