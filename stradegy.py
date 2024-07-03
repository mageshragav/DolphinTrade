import pandas as pd
from datetime import timedelta
# Load data from CSV
df = pd.read_csv('common/MachineLearningModel/output/five_mins/EURUSD_5_Min_testing.csv')

df['datetime'] = pd.to_datetime(df['datetime'])
df['UTC'] = df['datetime'] + timedelta(hours=5)

# Calculate GMT (UTC + 2 hours)
df['GMT'] = df['UTC'] + timedelta(hours=2)

# Define constants
MINOR_MIN_EXTREME_HEIGHT_ATRS = 2.0
MAJOR_TO_MINOR_HEIGHT_RATIO = 2.5
MINOR_MIN_EXTREME_WIDTH = 2
MAJOR_MIN_EXTREME_WIDTH = 2
RANGE_AVERAGING_PERIOD = 250
LINE_VALUE_DOWN = -1.0
LINE_VALUE_UP = 1.0
# Initialize columns for signals and other intermediate calculations
df['ATR'] = df['high'] - df['low']
df['ATR_SMA'] = df['ATR'].rolling(window=RANGE_AVERAGING_PERIOD).mean()
df['MinorMinExtremeHeight'] = df['ATR_SMA'] * MINOR_MIN_EXTREME_HEIGHT_ATRS
df['MajorMinExtremeHeight'] = df['MinorMinExtremeHeight'] * MAJOR_TO_MINOR_HEIGHT_RATIO
df['line1'] = 0.0
df['line2'] = 0.0
df['line3'] = 0.0
df['line4'] = 0.0
df['line5'] = 0.0

# Initialize state variables
minor_low_extreme_price = df['low'].iloc[0]
minor_hi_extreme_price = df['high'].iloc[0]
major_low_extreme_price = df['low'].iloc[0]
major_hi_extreme_price = df['high'].iloc[0]
minor_low_extreme_idx = 0
minor_hi_extreme_idx = 0
major_low_extreme_idx = 0
major_hi_extreme_idx = 0
minor_extreme_mode = 0
major_extreme_mode = 0
first_minor_low = True
first_minor_high = True
first_major_low = True
first_major_high = True

# Helper functions
def check_for_extremes(low_extreme_idx, low_extreme_price, hi_extreme_idx, hi_extreme_price, first_low, first_high, extreme_mode, min_extreme_height, min_extreme_width, current_idx, low, high, signal_type, df):
    signal = 0
    line_value = 0.0
    if idx >= 5386:
        print('hi')
    # Check for Bottom
    if extreme_mode > -1:
        if low < low_extreme_price:
            if not first_low:
                pass  # Erase extreme logic not needed in the current context
            low_extreme_price = low
            low_extreme_idx = current_idx
            first_low = False
        elif low > low_extreme_price:
            first_low = False
            if ((low - low_extreme_price) >= min_extreme_height) and ((current_idx - low_extreme_idx) >= min_extreme_width):
                extreme_mode = -1
                hi_extreme_price = high
                hi_extreme_idx = current_idx
                first_high = True
                first_low = True
                line_value = LINE_VALUE_DOWN
                if signal_type == 'minor':
                    signal = 1  # Minor buy signal
                    df.at[low_extreme_idx, 'line1'] = line_value
                else:
                    signal = 2  # Major buy signal
                    df.at[low_extreme_idx, 'line2'] = line_value

    # Check for Top
    if extreme_mode < 1:
        if high > hi_extreme_price:
            if not first_high:
                pass  # Erase extreme logic not needed in the current context
            hi_extreme_price = high
            hi_extreme_idx = current_idx
            first_high = False
        elif high < hi_extreme_price:
            first_high = False
            if ((hi_extreme_price - low) >= min_extreme_height) and ((current_idx - hi_extreme_idx) >= min_extreme_width):
                extreme_mode = 1
                low_extreme_price = low
                low_extreme_idx = current_idx
                first_high = True
                first_low = True
                line_value = LINE_VALUE_UP
                if signal_type == 'minor':
                    signal = -1  # Minor sell signal
                    df.at[hi_extreme_idx, 'line1'] = line_value
                else:
                    signal = -2  # Major sell signal
                    df.at[hi_extreme_idx, 'line2'] = line_value

    return low_extreme_idx, hi_extreme_idx, low_extreme_price, hi_extreme_price, first_low, first_high, extreme_mode, signal

# Process each row
for idx in range(0, len(df)):
    # Minor extremes
    minor_low_extreme_idx, minor_hi_extreme_idx, minor_low_extreme_price, minor_hi_extreme_price, first_minor_low, first_minor_high, minor_extreme_mode, minor_signal = check_for_extremes(
        minor_low_extreme_idx, minor_low_extreme_price,
        minor_hi_extreme_idx, minor_hi_extreme_price, first_minor_low, first_minor_high, minor_extreme_mode,
        df['MinorMinExtremeHeight'].iloc[idx], MINOR_MIN_EXTREME_WIDTH, idx, df['low'].iloc[idx], df['high'].iloc[idx], 'minor', df
    )

    # Major extremes
    major_low_extreme_idx, major_hi_extreme_idx, major_low_extreme_price, major_hi_extreme_price, first_major_low, first_major_high, major_extreme_mode, major_signal = check_for_extremes(
        major_low_extreme_idx, major_low_extreme_price,
        major_hi_extreme_idx, major_hi_extreme_price, first_major_low, first_major_high, major_extreme_mode,
        df['MajorMinExtremeHeight'].iloc[idx], MAJOR_MIN_EXTREME_WIDTH, idx, df['low'].iloc[idx], df['high'].iloc[idx], 'major', df
    )

# Save the result to a new CSV
df.to_csv("common/MachineLearningModel/output/test_result_5.csv", index=False)



###########################################



import pandas as pd
from datetime import timedelta
# Load data from CSV
df = pd.read_csv('common/MachineLearningModel/output/five_mins/EURUSD_5_Min_testing.csv')

df['datetime'] = pd.to_datetime(df['datetime'])
df['UTC'] = df['datetime'] + timedelta(hours=5)

# Calculate GMT (UTC + 2 hours)
df['GMT'] = df['UTC'] + timedelta(hours=2)

# Define constants
MINOR_MIN_EXTREME_HEIGHT_ATRS = 2.0
MAJOR_TO_MINOR_HEIGHT_RATIO = 2.5
MINOR_MIN_EXTREME_WIDTH = 2
MAJOR_MIN_EXTREME_WIDTH = 2
RANGE_AVERAGING_PERIOD = 250
# LINE_VALUE_DOWN = -1.0
# LINE_VALUE_UP = 1.0
LINE_MINOR = 'minor'
LINE_MAJOR = 'major'
LINE_SHADOW = 'shadow'
LINE_STABLE = 'stable'
NoRepaint = False
LINE_VALUE_UP = 1.0
LINE_VALUE_FLAT = 0.0
LINE_VALUE_DOWN = -1.0
# Initialize columns for signals and other intermediate calculations
df['ATR'] = df['high'] - df['low']
df['ATR_SMA'] = df['ATR'].rolling(window=RANGE_AVERAGING_PERIOD).mean()
df['MinorMinExtremeHeight'] = df['ATR_SMA'] * MINOR_MIN_EXTREME_HEIGHT_ATRS
df['MajorMinExtremeHeight'] = df['MinorMinExtremeHeight'] * MAJOR_TO_MINOR_HEIGHT_RATIO
df['line1'] = 0.0
df['line2'] = 0.0
df['line3'] = 0.0
df['line4'] = 0.0
df['line5'] = 0.0

# Initialize state variables
minor_low_extreme_price = df['low'].iloc[0]
minor_hi_extreme_price = df['high'].iloc[0]
major_low_extreme_price = df['low'].iloc[0]
major_hi_extreme_price = df['high'].iloc[0]
minor_low_extreme_idx = 0
minor_hi_extreme_idx = 0
major_low_extreme_idx = 0
major_hi_extreme_idx = 0
minor_extreme_mode = 0
major_extreme_mode = 0
first_minor_low = True
first_minor_high = True
first_major_low = True
first_major_high = True

def eraseExtreme(lineType, barIdx, value):
    drawShadow = (lineType == LINE_MAJOR) and (NoRepaint or (value == LINE_VALUE_UP and df['line1'].iloc[barIdx] != 0) or (value == LINE_VALUE_DOWN and df['line2'].iloc[barIdx] != 0))
    drawExtreme(lineType, barIdx, LINE_VALUE_FLAT)
    if drawShadow:
        draw(LINE_SHADOW, barIdx, value)

def drawExtreme(lineType, barIdx, value):
    if not NoRepaint:
        draw(lineType, barIdx, value)
        drawStableLine(lineType, barIdx, value)

def drawStableLine(lineType, barIdx, value):
    if lineType == LINE_MAJOR:
        return False
    draw(LINE_STABLE, barIdx, value)
    return True

def draw(lineType, barIdx, value):
    if lineType == LINE_MAJOR:
        updateLine('line1', 'line2', barIdx, value)
    elif lineType == LINE_MINOR:
        updateLine('line5', 'line5', barIdx, value)
    elif lineType == LINE_SHADOW:
        updateLine('line3', 'line3', barIdx, value)
    elif lineType == LINE_STABLE:
        updateLine('line4', 'line4', barIdx, value)

def updateLine(lineUp, lineDown, barIdx, value):
    if value in [LINE_VALUE_FLAT, LINE_VALUE_UP]:
        df.loc[barIdx, lineUp] = value
    if value in [LINE_VALUE_FLAT, LINE_VALUE_DOWN]:
        df.loc[barIdx, lineDown] = value

# Helper functions
def check_for_extremes(low_extreme_idx, low_extreme_price, hi_extreme_idx, hi_extreme_price, first_low, first_high, extreme_mode, min_extreme_height, min_extreme_width, current_idx, low, high, lineType, df):
    signal = 0
    line_value = 0.0
    # Check for Bottom
    if extreme_mode > -1:
        if low < low_extreme_price:
            if not first_low:
                eraseExtreme(lineType, low_extreme_idx, LINE_VALUE_DOWN)
            low_extreme_price = low
            low_extreme_idx = current_idx
            first_low = False
        elif low > low_extreme_price:
            drawExtreme(lineType, low_extreme_idx, LINE_VALUE_DOWN)
            first_low = False
            if ((low - low_extreme_price) >= min_extreme_height) and ((current_idx - low_extreme_idx) >= min_extreme_width):
                extreme_mode = -1
                hi_extreme_price = high
                hi_extreme_idx = current_idx
                first_high = True
                first_low = True
                line_value = LINE_VALUE_DOWN
                if NoRepaint:
                    draw(lineType, low_extreme_idx, LINE_VALUE_DOWN)
                drawStableLine(lineType, low_extreme_idx, LINE_VALUE_FLAT)
                # if signal_type == 'minor':
                #     signal = 1  # Minor buy signal
                #     df.at[low_extreme_idx, 'line1'] = line_value
                # else:
                #     signal = 2  # Major buy signal
                #     df.at[low_extreme_idx, 'line2'] = line_value

    # Check for Top
    if extreme_mode < 1:
        if high > hi_extreme_price:
            if not first_high:
                eraseExtreme(lineType, hi_extreme_idx, LINE_VALUE_UP)
            hi_extreme_price = high
            hi_extreme_idx = current_idx
            first_high = False
        elif high < hi_extreme_price:
            drawExtreme(lineType, hi_extreme_idx, LINE_VALUE_UP)
            first_high = False
            if ((hi_extreme_price - low) >= min_extreme_height) and ((current_idx - hi_extreme_idx) >= min_extreme_width):
                extreme_mode = 1
                low_extreme_price = low
                low_extreme_idx = current_idx
                first_high = True
                first_low = True
                line_value = LINE_VALUE_UP
                if NoRepaint:
                    draw(lineType, hi_extreme_idx, LINE_VALUE_UP)
                drawStableLine(lineType, hi_extreme_idx, LINE_VALUE_FLAT)
                # if signal_type == 'minor':
                #     signal = -1  # Minor sell signal
                #     df.at[hi_extreme_idx, 'line1'] = line_value
                # else:
                #     signal = -2  # Major sell signal
                #     df.at[hi_extreme_idx, 'line2'] = line_value

    return low_extreme_idx, hi_extreme_idx, low_extreme_price, hi_extreme_price, first_low, first_high, extreme_mode, signal

# Process each row
for idx in range(1, len(df)):
    # Minor extremes

    minor_low_extreme_idx, minor_hi_extreme_idx, minor_low_extreme_price, minor_hi_extreme_price, first_minor_low, first_minor_high, minor_extreme_mode, minor_signal = check_for_extremes(
        minor_low_extreme_idx, minor_low_extreme_price,
        minor_hi_extreme_idx, minor_hi_extreme_price, first_minor_low, first_minor_high, minor_extreme_mode,
        df['MinorMinExtremeHeight'].iloc[idx], MINOR_MIN_EXTREME_WIDTH, idx, df['low'].iloc[idx], df['high'].iloc[idx], 'minor', df
    )

    # Major extremes

    major_low_extreme_idx, major_hi_extreme_idx, major_low_extreme_price, major_hi_extreme_price, first_major_low, first_major_high, major_extreme_mode, major_signal = check_for_extremes(
        major_low_extreme_idx, major_low_extreme_price,
        major_hi_extreme_idx, major_hi_extreme_price, first_major_low, first_major_high, major_extreme_mode,
        df['MajorMinExtremeHeight'].iloc[idx], MAJOR_MIN_EXTREME_WIDTH, idx, df['low'].iloc[idx], df['high'].iloc[idx], 'major', df
    )

# Save the result to a new CSV
df.to_csv("common/MachineLearningModel/output/test_result_8.csv", index=False)
