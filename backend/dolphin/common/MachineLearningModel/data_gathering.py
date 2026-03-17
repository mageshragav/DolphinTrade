# Welcome to Alpha Vantage! Here is your API key: AI0V2OFUA8YIDWXF. Please record this API key at a safe place for future data access.
# API key: AI0V2OFUA8YIDWXF

# importing libraries
import pandas as pd
from TradingDataGenerate import TvDatafeed, Interval


class DataGathering:
    
    def __init__(self) -> None:
        self.tradingview_obj = TvDatafeed()
        self.histroy_data = self.GettingTradingData()

    def get_history(self,symbol,exchange,interval,bars) -> pd.DataFrame:
        response_df = self.tradingview_obj.get_hist(symbol=symbol,exchange=exchange,interval=interval,n_bars=bars,extended_session=True)
        return response_df

    def GettingTradingData(self):
        response_data = self.get_history('EURJPY','FX_IDC',Interval.in_5_minute,10000)
        return response_data
    
    def GenerateCsv(self):
        self.histroy_data.to_csv('EURJPY_5_Min.csv')


    
