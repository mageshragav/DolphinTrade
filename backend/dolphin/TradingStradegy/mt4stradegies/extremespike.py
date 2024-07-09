import pandas as pd
from datetime import timedelta

class ExtremeSpike:
    def __init__(self,df: pd.DataFrame,assest:str) -> None:
        self.df = df.copy()
        # self.df['datetime'] = pd.to_datetime(self.df['datetime'])
        # self.df['UTC'] = self.df['datetime'] + timedelta(hours=5)

        # # Calculate GMT (UTC + 2 hours)
        # self.df['GMT'] = self.df['UTC'] + timedelta(hours=2)
        # Define constants
        self.MINOR_MIN_EXTREME_HEIGHT_ATRS = 2.0
        self.MAJOR_TO_MINOR_HEIGHT_RATIO = 2.5
        self.MINOR_MIN_EXTREME_WIDTH = 2
        self.MAJOR_MIN_EXTREME_WIDTH = 2
        self.RANGE_AVERAGING_PERIOD = 250
        # LINE_VALUE_DOWN = -1.0
        # LINE_VALUE_UP = 1.0
        self.LINE_MINOR = 'minor'
        self.LINE_MAJOR = 'major'
        self.LINE_SHADOW = 'shadow'
        self.LINE_STABLE = 'stable'
        self.NoRepaint = False
        self.LINE_VALUE_UP = 1.0
        self.LINE_VALUE_FLAT = 0.0
        self.LINE_VALUE_DOWN = -1.0
        # Initialize columns for signals and other intermediate calculations
        self.df['ATR'] = self.df['high'] - self.df['low']
        self.df['ATR_SMA'] = self.df['ATR'].rolling(window=self.RANGE_AVERAGING_PERIOD).mean()
        self.df['MinorMinExtremeHeight'] = self.df['ATR_SMA'] * self.MINOR_MIN_EXTREME_HEIGHT_ATRS
        self.df['MajorMinExtremeHeight'] = self.df['MinorMinExtremeHeight'] * self.MAJOR_TO_MINOR_HEIGHT_RATIO
        self.df['line1'] = 0.0
        self.df['line2'] = 0.0
        self.df['line3'] = 0.0
        self.df['line4'] = 0.0
        self.df['line5'] = 0.0
        # Initialize state variables
        self.minor_low_extreme_price = self.df['low'].iloc[0]
        self.minor_hi_extreme_price = self.df['high'].iloc[0]
        self.major_low_extreme_price = self.df['low'].iloc[0]
        self.major_hi_extreme_price = self.df['high'].iloc[0]
        self.minor_low_extreme_idx = 0
        self.minor_hi_extreme_idx = 0
        self.major_low_extreme_idx = 0
        self.major_hi_extreme_idx = 0
        self.minor_extreme_mode = 0
        self.major_extreme_mode = 0
        self.first_minor_low = True
        self.first_minor_high = True
        self.first_major_low = True
        self.first_major_high = True

    def eraseExtreme(self,lineType, barIdx, value):
        drawShadow = (lineType == self.LINE_MAJOR) and (self.NoRepaint or (value == self.LINE_VALUE_UP and self.df['line1'].iloc[barIdx] != 0) or (value == self.LINE_VALUE_DOWN and self.df['line2'].iloc[barIdx] != 0))
        self.drawExtreme(lineType, barIdx, self.LINE_VALUE_FLAT)
        if drawShadow:
            self.draw(self.LINE_SHADOW, barIdx, value)

    def drawExtreme(self,lineType, barIdx, value):
        if not self.NoRepaint:
            self.draw(lineType, barIdx, value)
            self.drawStableLine(lineType, barIdx, value)

    def drawStableLine(self,lineType, barIdx, value):
        if lineType == self.LINE_MAJOR:
            return False
        self.draw(self.LINE_STABLE, barIdx, value)
        return True

    def draw(self, lineType, barIdx, value):
        if lineType == self.LINE_MAJOR:
            self.updateLine('line1', 'line2', barIdx, value)
        elif lineType == self.LINE_MINOR:
            self.updateLine('line5', 'line5', barIdx, value)
        elif lineType == self.LINE_SHADOW:
            self.updateLine('line3', 'line3', barIdx, value)
        elif lineType == self.LINE_STABLE:
            self.updateLine('line4', 'line4', barIdx, value)

    def updateLine(self, lineUp, lineDown, barIdx, value):
        if value in [self.LINE_VALUE_FLAT, self.LINE_VALUE_UP]:
            self.df.loc[barIdx, lineUp] = value
        if value in [self.LINE_VALUE_FLAT, self.LINE_VALUE_DOWN]:
            self.df.loc[barIdx, lineDown] = value

    # Helper functions
    def check_for_extremes(self,low_extreme_idx, low_extreme_price, hi_extreme_idx, hi_extreme_price, first_low, first_high, extreme_mode, min_extreme_height, min_extreme_width, current_idx, low, high, lineType, df):
        signal = 0
        line_value = 0.0
        # Check for Bottom
        if extreme_mode > -1:
            if low < low_extreme_price:
                if not first_low:
                    self.eraseExtreme(lineType, low_extreme_idx, self.LINE_VALUE_DOWN)
                low_extreme_price = low
                low_extreme_idx = current_idx
                first_low = False
            elif low > low_extreme_price:
                self.drawExtreme(lineType, low_extreme_idx, self.LINE_VALUE_DOWN)
                first_low = False
                if ((low - low_extreme_price) >= min_extreme_height) and ((current_idx - low_extreme_idx) >= min_extreme_width):
                    extreme_mode = -1
                    hi_extreme_price = high
                    hi_extreme_idx = current_idx
                    first_high = True
                    first_low = True
                    line_value = self.LINE_VALUE_DOWN
                    if self.NoRepaint:
                        self.draw(lineType, low_extreme_idx, self.LINE_VALUE_DOWN)
                    self.drawStableLine(lineType, low_extreme_idx, self.LINE_VALUE_FLAT)
                    # if lineType == self.LINE_MINOR:
                    #     signal = 1  # Minor buy signal
                    #     df.at[low_extreme_idx, 'line1'] = line_value
                    # else:
                    #     signal = 2  # Major buy signal
                    #     df.at[low_extreme_idx, 'line2'] = line_value

        # Check for Top
        if extreme_mode < 1:
            if high > hi_extreme_price:
                if not first_high:
                    self.eraseExtreme(lineType, hi_extreme_idx, self.LINE_VALUE_UP)
                hi_extreme_price = high
                hi_extreme_idx = current_idx
                first_high = False
            elif high < hi_extreme_price:
                self.drawExtreme(lineType, hi_extreme_idx, self.LINE_VALUE_UP)
                first_high = False
                if ((hi_extreme_price - low) >= min_extreme_height) and ((current_idx - hi_extreme_idx) >= min_extreme_width):
                    extreme_mode = 1
                    low_extreme_price = low
                    low_extreme_idx = current_idx
                    first_high = True
                    first_low = True
                    line_value = self.LINE_VALUE_UP
                    if self.NoRepaint:
                        self.draw(lineType, hi_extreme_idx, self.LINE_VALUE_UP)
                    self.drawStableLine(lineType, hi_extreme_idx, self.LINE_VALUE_FLAT)
                    # if lineType == self.LINE_MINOR:
                    #     signal = -1  # Minor sell signal
                    #     df.at[hi_extreme_idx, 'line1'] = line_value
                    # else:
                    #     signal = -2  # Major sell signal
                    #     df.at[hi_extreme_idx, 'line2'] = line_value

        return low_extreme_idx, hi_extreme_idx, low_extreme_price, hi_extreme_price, first_low, first_high, extreme_mode, signal

    def mainloop(self):
        # Process each row
        for idx in range(1, len(self.df)):
            # Minor extremes

            self.minor_low_extreme_idx, self.minor_hi_extreme_idx, self.minor_low_extreme_price, self.minor_hi_extreme_price, self.first_minor_low, self.first_minor_high, self.minor_extreme_mode, minor_signal = self.check_for_extremes(
                self.minor_low_extreme_idx, self.minor_low_extreme_price,
                self.minor_hi_extreme_idx, self.minor_hi_extreme_price, self.first_minor_low, self.first_minor_high, self.minor_extreme_mode,
                self.df['MinorMinExtremeHeight'].iloc[idx], self.MINOR_MIN_EXTREME_WIDTH, idx, self.df['low'].iloc[idx], self.df['high'].iloc[idx], 'minor', self.df
            )

            # Major extremes

            self.major_low_extreme_idx, self.major_hi_extreme_idx, self.major_low_extreme_price, self.major_hi_extreme_price, self.first_major_low, self.first_major_high, self.major_extreme_mode, major_signal = self.check_for_extremes(
                self.major_low_extreme_idx, self.major_low_extreme_price,
                self.major_hi_extreme_idx, self.major_hi_extreme_price, self.first_major_low, self.first_major_high, self.major_extreme_mode,
                self.df['MajorMinExtremeHeight'].iloc[idx], self.MAJOR_MIN_EXTREME_WIDTH, idx, self.df['low'].iloc[idx], self.df['high'].iloc[idx], 'major', self.df
            )

        return self.df[['line1','line2','line4','line5']]
