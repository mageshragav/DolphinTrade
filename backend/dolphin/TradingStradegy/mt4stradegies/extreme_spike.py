import pandas as pd
from datetime import timedelta
import numpy as np
# stradegy No. 1 ExtremeSpike
# Description: 
    # The Extreme Spike is a price-action-based technical indicator used to identify highly probable bullish and bearish spike signals in MT4.
    # In financial trading, a spike means a one-direction, aggressive and extensive price movement within a very short spell. Both day and  
    # intraday traders consider this price action an opportunity to make quick and handsome profits. However, it’s not always easy to spot solid 
    # spikes since no one knows when it will happen and in which direction the price may continue to move. Besides, you can sit in front of the 
    # chart all day long, waiting for a sharp price movement. The Extreme Spike indicator closely monitors the price behavior and 
    # alerts on potential market trends ahead. Besides, it detects market high-low and points to critical price swing zones. 
    # This article will explain how to use the Extreme Spike Indicator in MT4 to make profitable buy-sell decisions

class ExtremeSpikeSignalPredictor:
    def __init__(self,df: pd.DataFrame) -> None:
        self.df = df.copy()
        self.df['t'] = self.df['datetime']
        self.df['t'] = pd.to_datetime(self.df['t'])
        # self.df['UTC'] = self.df['t'] + timedelta(hours=5)
        # Calculate GMT (UTC + 2 hours)
        self.df['GMT'] = self.df['t'] + timedelta(hours=2)
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
        self.NoRepaint = True
        self.LINE_VALUE_UP = 1
        self.LINE_VALUE_FLAT = 0
        self.LINE_VALUE_DOWN = 2
        # Initialize columns for signals and other intermediate calculations
        self.df['ATR'] = self.df['high'] - self.df['low']
        self.df['ATR_SMA'] = self.df['ATR'].rolling(window=self.RANGE_AVERAGING_PERIOD).mean()
        self.df['MinorMinExtremeHeight'] = self.df['ATR_SMA'] * self.MINOR_MIN_EXTREME_HEIGHT_ATRS
        self.df['MajorMinExtremeHeight'] = self.df['MinorMinExtremeHeight'] * self.MAJOR_TO_MINOR_HEIGHT_RATIO
        self.df.loc[:,'line1'] = 0
        self.df.loc[:,'line2'] = 0
        self.df.loc[:,'line3'] = 0
        self.df.loc[:,'line4'] = 0
        self.df.loc[:,'line5'] = 0
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
        self.minor = {
            "low_extreme_price": self.df['low'].iloc[0],
            "hi_extreme_price": self.df['high'].iloc[0],
            "low_extreme_idx": 0,
            "hi_extreme_idx": 0,
            "extreme_mode": 0,
            "first_low": 0,
            "first_high": 0,
        }
        self.major = {
            "low_extreme_price": self.df['low'].iloc[0],
            "hi_extreme_price": self.df['high'].iloc[0],
            "low_extreme_idx": 0,
            "hi_extreme_idx": 0,
            "extreme_mode": 0,
            "first_low": 0,
            "first_high": 0,
        }

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
    # def check_for_extremes(self,ex_dict,low_extreme_idx, low_extreme_price, hi_extreme_idx, hi_extreme_price, first_low, first_high, extreme_mode, min_extreme_height, min_extreme_width, current_idx, low, high, lineType, df):
    def check_for_extremes(self,ex_dict,min_extreme_height, min_extreme_width, current_idx, low, high, lineType, df):
        signal = 0
        line_value = 0.0
        # Check for Bottom
        if ex_dict['extreme_mode'] > -1:
            if low < ex_dict['low_extreme_price']:
                if not ex_dict['first_low']:
                    self.eraseExtreme(lineType, ex_dict['low_extreme_idx'], self.LINE_VALUE_DOWN)
                ex_dict['low_extreme_price'] = low
                ex_dict['low_extreme_idx'] = current_idx
                ex_dict['first_low'] = False
            elif low > ex_dict['low_extreme_price']:
                self.drawExtreme(lineType, ex_dict['low_extreme_idx'], self.LINE_VALUE_DOWN)
                ex_dict['first_low'] = False
                if ((low - ex_dict['low_extreme_price']) >= min_extreme_height) and ((current_idx - ex_dict['low_extreme_idx']) >= min_extreme_width):
                    ex_dict['extreme_mode'] = -1
                    ex_dict['hi_extreme_price'] = high
                    ex_dict['hi_extreme_idx'] = current_idx
                    ex_dict['first_high'] = True
                    ex_dict['first_low'] = True
                    line_value = self.LINE_VALUE_DOWN
                    if self.NoRepaint:
                        self.draw(lineType, ex_dict['low_extreme_idx'], self.LINE_VALUE_DOWN)
                    self.drawStableLine(lineType, ex_dict['low_extreme_idx'], self.LINE_VALUE_FLAT)

        # Check for Top
        if ex_dict['extreme_mode'] < 1:
            if high > ex_dict['hi_extreme_price']:
                if not ex_dict['first_high']:
                    self.eraseExtreme(lineType, ex_dict['hi_extreme_idx'], self.LINE_VALUE_UP)
                ex_dict['hi_extreme_price'] = high
                ex_dict['hi_extreme_idx'] = current_idx
                ex_dict['first_high'] = False
            elif high < ex_dict['hi_extreme_price']:
                self.drawExtreme(lineType, ex_dict['hi_extreme_idx'], self.LINE_VALUE_UP)
                ex_dict['first_high'] = False
                if ((ex_dict['hi_extreme_price'] - low) >= min_extreme_height) and ((current_idx - ex_dict['hi_extreme_idx']) >= min_extreme_width):
                    ex_dict['extreme_mode'] = 1
                    ex_dict['low_extreme_price'] = low
                    ex_dict['low_extreme_idx'] = current_idx
                    ex_dict['first_high'] = True
                    ex_dict['first_low'] = True
                    line_value = self.LINE_VALUE_UP
                    if self.NoRepaint:
                        self.draw(lineType, ex_dict['hi_extreme_idx'], self.LINE_VALUE_UP)
                    self.drawStableLine(lineType, ex_dict['hi_extreme_idx'], self.LINE_VALUE_FLAT)

    def run(self):
        # Process each row
        for idx in range(1, len(self.df)):
            # Minor extremes
            self.check_for_extremes(
                self.minor,
                self.df['MinorMinExtremeHeight'].iloc[idx], self.MINOR_MIN_EXTREME_WIDTH, idx, self.df['low'].iloc[idx], self.df['high'].iloc[idx], 'minor', self.df
            )

            # Major extremes
            self.check_for_extremes(
                self.major,
                self.df['MajorMinExtremeHeight'].iloc[idx], self.MAJOR_MIN_EXTREME_WIDTH, idx, self.df['low'].iloc[idx], self.df['high'].iloc[idx], 'major', self.df
            )
        # self.df.to_csv('/tmp/extremespike.csv')
        # return self.df[['line1','line2','line4', 'line5']]
        return self.df
