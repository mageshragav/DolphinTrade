import pandas as pd 
import numpy as np
from decimal import Decimal
from datetime import timedelta,datetime
import pandas as pd 
import numpy as np
from decimal import Decimal
from datetime import timedelta,datetime
# class BinaryArrowSignalPredictor:
#     def __init__(self, df: pd.DataFrame) -> None:
#         self.df = df.copy()
#         # Define parameters
#         self.SignalGap = 20
#         self.BarsToCount = len(df)
#         self.dist = 24
#         decimal_places = len(str(self.df['close'].iloc[0]).split('.')[-1])
#         self.Point = float(Decimal(f"0.{'0' * (decimal_places - 1)}1"))  # Assuming Point is 0.00001 for Forex pairs, adjust as needed

#         # Initialize columns for signals
#         self.df.loc[:,'BinaryArrow'] = 0

#     def ihighest(self, highs: pd.Series, period: int, shift: int) -> int:
#         """Find the index of the highest high in a given range."""
#         if shift < 0 or shift + period > len(highs):
#             return np.nan
#         return highs.iloc[shift:shift + period].idxmax()

#     def ilowest(self, lows: pd.Series, period: int, shift: int) -> int:
#         """Find the index of the lowest low in a given range."""
#         if shift < 0 or shift + period > len(lows):
#             return np.nan
#         return lows.iloc[shift:shift + period].idxmin()

#     def run(self) -> None:
#         """Calculate buy and sell signals and update DataFrame."""
#         high_series = self.df['high']
#         low_series = self.df['low']
        
#         # Calculate highest high and lowest low
#         for i in range(self.BarsToCount,1, -1):
#             hhb = self.ihighest(high_series, self.dist, i - self.dist // 2)
#             llb = self.ilowest(low_series, self.dist, i - self.dist // 2)
            
#             if pd.notna(hhb) and i == hhb:
#                 self.df.at[self.df.index[i], 'BinaryArrow'] = 2
#             if pd.notna(llb) and i == llb:
#                 self.df.at[self.df.index[i], 'BinaryArrow'] = 1

#         return self.df

class BinaryArrowSignalPredictor:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        # Define parameters
        self.SignalGap = 20
        self.BarsToCount = len(df)
        self.dist = 24
        decimal_places = len(str(self.df['close'].iloc[0]).split('.')[-1])
        self.Point = float(Decimal(f"0.{'0' * (decimal_places - 1)}1"))  # Assuming Point is 0.00001 for Forex pairs, adjust as needed

        # Initialize columns for signals
        self.df.loc[:,'BinaryArrow'] = 0

    def ihighest(self, highs: pd.Series, period: int, shift: int) -> int:
        """Find the index of the highest high in a given range."""
        if shift < 0 or shift + period > len(highs):
            return np.nan
        return highs.iloc[shift:shift + period].idxmax()

    def ilowest(self, lows: pd.Series, period: int, shift: int) -> int:
        """Find the index of the lowest low in a given range."""
        if shift < 0 or shift + period > len(lows):
            return np.nan
        return lows.iloc[shift:shift + period].idxmin()

    def run(self) -> pd.DataFrame:
        """Calculate buy and sell signals and update DataFrame."""
        high_series = self.df['high']
        low_series = self.df['low']
        
        # Calculate highest high and lowest low
        for i in range(self.BarsToCount,1, -1):
            hhb = self.ihighest(high_series, self.dist, i - self.dist // 2)
            llb = self.ilowest(low_series, self.dist, i - self.dist // 2)
            
            if pd.notna(hhb) and i == hhb:
                self.df.at[self.df.index[i], 'BinaryArrow'] = 2
            if pd.notna(llb) and i == llb:
                self.df.at[self.df.index[i], 'BinaryArrow'] = 1

        return self.df
