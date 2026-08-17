import pandas as pd


class BinaryArrowSignalPredictor:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df.copy()
        # Define parameters
        self.SignalGap = 20
        self.BarsToCount = len(df)
        self.dist = 24

        # Initialize columns for signals
        self.df.loc[:, 'BinaryArrow'] = 0

    def run(self) -> pd.DataFrame:
        """Calculate buy and sell signals and update DataFrame.

        Lookback-only: a signal is confirmed at bar i using only bars up to
        and including i (no future bars), so the newest bar always has a
        valid value and the indicator never repaints.
        """
        high_series = self.df['high']
        low_series = self.df['low']

        for i in range(self.dist, len(self.df)):
            hhb = high_series.iloc[i - self.dist + 1: i + 1].idxmax()
            llb = low_series.iloc[i - self.dist + 1: i + 1].idxmin()
            if i == hhb:
                self.df.at[self.df.index[i], 'BinaryArrow'] = 2
            if i == llb:
                self.df.at[self.df.index[i], 'BinaryArrow'] = 1

        return self.df
