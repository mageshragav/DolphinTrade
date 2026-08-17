"""MQL4-derived lookback-only features ported from mt4indicators/later/.

Every feature here is causally computable from bars up to and including the
current row (no close[0] leakage, no centered windows, no future bars) and is
verified by the truncation-invariance test in tests/test_mql_features.py.

Ported ideas (source file -> what we took):
  Brooky psar levels     -> PSAR(0.02/0.2) vs close + flip S/R level distance
  Flat Pulse             -> Bollinger-width/ATR regime ratio + regression slope
  Candlestick alerts     -> 10-pattern candle library + EMA5 slope filter
  ReversalFractals       -> 5-bar fractal reversal with buy/sell alternation
  Enigma_Scalper_Arrows  -> confirmed outside-bar reversal after 3-bar slide
  EMA MACD indi          -> MACD(10,20,7) zero-cross state gated by EMA13
  FiboPiv-v2             -> fib-weighted daily pivots (P/R1/R2/R3, S1/S2/S3)
  fibo retracement 1.01  -> causal ZigZag(30,5pt,3) + distance to 61.8% level
  alex_v1_1              -> 8-bar high/low channel-midline distance + crosses
  forecast_osc-30M       -> T3-filtered forecast oscillator (closed-form linreg)

All functions take a frame with columns datetime,symbol,open,high,low,close
[,volume] and return a DataFrame of new columns named mql_*.
"""

import numpy as np
import pandas as pd
import ta

PSAR_STEP = 0.02
PSAR_MAX = 0.2

REG_WINDOW = 20      # Flat Pulse regression window
MID_WINDOW = 8       # alex_v1_1 channel midline window
MACD_F, MACD_S, MACD_SIG = 10, 20, 7
ZZ_DEPTH = 30        # ZigZag pivot depth (bars)
ZZ_BACKSTEP = 3      # ZigZag confirmation backstep
EME_WINDOW = 3       # EMA MACD indi EMA13 vs EMA10/20... uses 13
FIB_LEVELS = {'r1': 0.382, 'r2': 0.618, 'r3': 1.000}


def _atr_safe(h, l, c):
    if len(h) < 15:
        return pd.Series(np.nan, index=h.index)
    atr = ta.volatility.average_true_range(h, l, c, window=14)
    return atr.replace(0, np.nan)


def _rolling_slope(y, window):
    """Closed-form rolling OLS slope of y vs bar position (causal)."""
    pos = pd.Series(np.arange(len(y)), index=y.index)
    mean_y = y.rolling(window).mean()
    mean_pos = pos.rolling(window).mean()
    py = pos * y
    cov = py.rolling(window).mean() - mean_pos * mean_y
    var_x = (window * window - 1) / 12.0
    return cov / var_x


def _psar(h, l, step=PSAR_STEP, max_step=PSAR_MAX):
    """Standard PSAR recursion (causal). Returns sar array."""
    n = len(h)
    sar = np.full(n, np.nan)
    ep = np.full(n, np.nan)
    af = np.full(n, np.nan)
    bull = np.zeros(n, dtype=bool)
    sar[0], ep[0], af[0], bull[0] = l[0], h[0], step, True
    for i in range(1, n):
        prev = sar[i - 1] + af[i - 1] * (ep[i - 1] - sar[i - 1])
        if bull[i - 1]:
            sar[i] = min(prev, l[i - 1], l[i - 2] if i >= 2 else l[i - 1])
            if h[i] > ep[i - 1]:
                ep[i], af[i] = h[i], min(af[i - 1] + step, max_step)
            else:
                ep[i], af[i] = ep[i - 1], af[i - 1]
            if l[i] < sar[i]:
                bull[i], sar[i], ep[i], af[i] = False, ep[i - 1], l[i], step
            else:
                bull[i] = True
        else:
            sar[i] = max(prev, h[i - 1], h[i - 2] if i >= 2 else h[i - 1])
            if l[i] < ep[i - 1]:
                ep[i], af[i] = l[i], min(af[i - 1] + step, max_step)
            else:
                ep[i], af[i] = ep[i - 1], af[i - 1]
            if h[i] > sar[i]:
                bull[i], sar[i], ep[i], af[i] = True, ep[i - 1], h[i], step
            else:
                bull[i] = False
    return sar


def psar_features(df, atr):
    """PSAR vs close position, signed bars since last flip, S/R level distance."""
    h, l, c = df['high'], df['low'], df['close']
    sar = pd.Series(np.nan, index=df.index)
    for sym, g in df.groupby('symbol', sort=False):
        sar.loc[g.index] = _psar(g['high'].values, g['low'].values)
    side = (sar < c).astype(int) * 2 - 1            # +1 bullish
    side = side.where(sar.notna())
    flip = (side != side.shift(1)) & side.notna() & side.shift(1).notna()

    f = pd.DataFrame(index=df.index)
    f['mql_sar_dist_atr'] = (c - sar) / atr
    # signed bars since last flip; sign = current PSAR side
    flip_pos = np.where(flip.fillna(False).values, np.arange(len(df)), -1)
    last = np.maximum.accumulate(flip_pos)
    since = np.where(last >= 0, np.arange(len(df)) - last, np.nan)
    f['mql_sar_flip_since'] = since * side.values
    # S/R level drawn at last flip = PSAR value on the flip bar
    sar_arr = sar.values
    flip_val = np.where(flip.fillna(False).values, sar_arr, np.nan)
    last_val = _ffill_np(flip_val)
    f['mql_sar_level_dist_atr'] = (c - last_val) / atr
    return f


def _ffill_np(arr):
    out = np.full(len(arr), np.nan)
    prev = np.nan
    for i in range(len(arr)):
        if not np.isnan(arr[i]):
            prev = arr[i]
        out[i] = prev
    return out


def regime_features(df, atr):
    """Flat Pulse: Bollinger-width/ATR ratio (bbs) + 20-bar regression slope."""
    c = df['close']
    bb_mid = c.rolling(10).mean()
    bb_std = c.rolling(10).std()
    bb_width = bb_mid + 2 * bb_std - (bb_mid - 2 * bb_std)
    f = pd.DataFrame(index=df.index)
    f['mql_bb_atr_ratio'] = bb_width / (atr * 1.5)
    slope = _rolling_slope(c, REG_WINDOW)
    f['mql_reg_slope_atr'] = slope * REG_WINDOW / atr
    return f


def _pattern_flags(o, h, l, c):
    """10 candle patterns on closed bars (Candlestick alerts port)."""
    body = (c - o).abs()
    rng = (h - l).replace(0, np.nan)
    bull = c > o
    bear = c < o
    body_sm = body / rng

    # engulfing
    eng_bull = bull & bear.shift(1) & (c >= o.shift(1)) & (o <= c.shift(1))
    eng_bear = bear & bull.shift(1) & (c <= o.shift(1)) & (o >= c.shift(1))
    # harami (small body inside prior body)
    har_bull = bull & bear.shift(1) & (o >= c.shift(1)) & (c <= o.shift(1)) \
        & (body < body.shift(1))
    har_bear = bear & bull.shift(1) & (o <= c.shift(1)) & (c >= o.shift(1)) \
        & (body < body.shift(1))
    # piercing / dark cloud
    mid_prev = (h.shift(1) + l.shift(1)) / 2
    pierce = bull & bear.shift(1) & (c > mid_prev) & (c < o.shift(1))
    dark_c = bear & bull.shift(1) & (c < mid_prev) & (c > o.shift(1))
    # morning / evening star (small middle body)
    sm = body_sm.shift(1) < 0.3
    mom_star = bull & sm & bear.shift(2) & (c > mid_prev.shift(1))
    eve_star = bear & sm & bull.shift(2) & (c < mid_prev.shift(1))
    # hammer / shooting star (long wick, small body at opposite end)
    upper = h - np.maximum(c, o)
    lower = np.minimum(c, o) - l
    hammer = bull & (body_sm <= 0.35) & (lower >= 2 * body) & (upper <= 0.3 * body)
    shoot = bear & (body_sm <= 0.35) & (upper >= 2 * body) & (lower <= 0.3 * body)

    out = pd.DataFrame(index=o.index)
    out['bull'] = (eng_bull | har_bull | pierce | mom_star | hammer).astype(int)
    out['bear'] = (eng_bear | har_bear | dark_c | eve_star | shoot).astype(int)
    return out


def candle_features(df, atr):
    """Pattern counts over last 3 bars + last pattern direction + EMA5 slope."""
    c = df['close']
    pat = _pattern_flags(df['open'], df['high'], df['low'], c)
    bull3 = pat['bull'].rolling(3).sum()
    bear3 = pat['bear'].rolling(3).sum()
    f = pd.DataFrame(index=df.index)
    f['mql_pat_bull3'] = bull3
    f['mql_pat_bear3'] = bear3
    last_dir = (pat['bull'] - pat['bear']).replace(0, np.nan)
    f['mql_pat_last'] = last_dir
    ema5 = ta.trend.ema_indicator(c, window=5)
    f['mql_ema5_slope_atr'] = (ema5 - ema5.shift(3)) / atr
    return f


def fractal_features(df, atr):
    """5-bar fractal reversals with strict buy/sell alternation."""
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    # causal 5-bar fractal confirmation at pivot p is known at bar p+2
    l2, l1, l3, l4 = l.shift(2), l.shift(1), l.shift(3), l.shift(4)
    fract_down = (l2 < l1) & (l2 < l3) & (l2 < l4) & (l2 < l)
    h2, h1, h3, h4 = h.shift(2), h.shift(1), h.shift(3), h.shift(4)
    fract_up = (h2 > h1) & (h2 > h3) & (h2 > h4) & (h2 > h)

    n = len(df)
    since = np.full(n, np.nan)
    level = np.full(n, np.nan)
    dirn = np.zeros(n)
    for sym, g in df.groupby('symbol', sort=False):
        s = list(g.index)                       # labels == positions (RangeIndex)
        cur_dir = 0
        for j, i in enumerate(s):
            if fract_down.loc[i] and cur_dir != 1:
                cur_dir, since[j], level[j] = 1, 0, l2.loc[i]
            elif fract_up.loc[i] and cur_dir != -1:
                cur_dir, since[j], level[j] = -1, 0, h2.loc[i]
            elif j > 0:
                since[j] = since[j - 1] + 1 if not np.isnan(since[j - 1]) else np.nan
                level[j] = level[j - 1]
            dirn[j] = cur_dir
    f = pd.DataFrame(index=df.index)
    f['mql_frac_since'] = pd.Series(since, index=df.index) * pd.Series(dirn, index=df.index)
    f['mql_frac_level_atr'] = (df['close'] - pd.Series(level, index=df.index)) / atr
    return f


def outside_reversal_features(df):
    """Enigma: 3-bar slide + close back through pivot high/low."""
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    slide_dn = (l.shift(4) >= l.shift(3)) & (l.shift(3) >= l.shift(2))
    slide_up = (h.shift(4) <= h.shift(3)) & (h.shift(3) <= h.shift(2))
    rev_bull = slide_dn & (c.shift(1) > l.shift(2)) & (c.shift(1) > h.shift(2))
    rev_bear = slide_up & (c.shift(1) < h.shift(2)) & (c.shift(1) < l.shift(2))
    f = pd.DataFrame(index=df.index)
    f['mql_outrev_bull'] = rev_bull.astype(int)
    f['mql_outrev_bear'] = rev_bear.astype(int)
    sig = (rev_bull.astype(int) - rev_bear.astype(int)).replace(0, np.nan)
    sig_pos = sig.notna()
    last = np.where(sig_pos.values, np.arange(len(df)), -1)
    last = np.maximum.accumulate(last)
    since = np.where(last >= 0, np.arange(len(df)) - last, np.nan)
    dirn = np.where(sig.fillna(0).values == 0, 0, np.sign(sig.fillna(0).values))
    f['mql_outrev_since'] = since * dirn
    return f


def macd_ema_features(df, atr):
    """MACD(10,20,7) zero-cross state gated by EMA13 trend."""
    c = df['close']
    macd_line = ta.trend.macd(c, window_fast=MACD_F, window_slow=MACD_S)
    macd_sig = ta.trend.macd_signal(c, window_fast=MACD_F, window_slow=MACD_S,
                                    window_sign=MACD_SIG)
    macd = macd_line - macd_sig
    ema13 = ta.trend.ema_indicator(c, window=13)
    state = np.where((macd > 0) & (c > ema13), 1,
                     np.where((macd < 0) & (c < ema13), -1, 0))
    cross = ((macd > 0) & (macd.shift(1) <= 0)).astype(int) \
        - ((macd < 0) & (macd.shift(1) >= 0)).astype(int)
    cross_pos = cross != 0
    last = np.where(cross_pos.values, np.arange(len(df)), -1)
    last = np.maximum.accumulate(last)
    since = np.where(last >= 0, np.arange(len(df)) - last, np.nan)
    dirn = np.where(cross.fillna(0).values == 0, 0, np.sign(cross.fillna(0).values))
    f = pd.DataFrame(index=df.index)
    f['mql_macd_state'] = state
    f['mql_macd_cross_since'] = since * dirn
    f['mql_macd_hist_atr'] = (macd - macd.shift(1)) / atr
    return f


def fibo_pivot_features(df, atr):
    """FiboPiv: prev-day P/R1-R3/S1-S3; close position + level distances.

    Every value comes from the day STRICTLY BEFORE the current row's day, so
    the feature is invariant to truncating the frame (no current-day leak).
    Positional-only arithmetic (no label alignment) so symbol slices with
    offset index labels stay correct.
    """
    dt = df['datetime']
    d = dt.dt.date
    day_grp = pd.DataFrame({
        'symbol': df['symbol'].values, 'date': d.values,
        'high': df['high'].values, 'low': df['low'].values,
        'close': df['close'].values,
    })
    daily = day_grp.groupby(['symbol', 'date'], sort=False).agg(
        high=('high', 'max'), low=('low', 'min'), close=('close', 'last'))
    daily = daily.reset_index().sort_values(['symbol', 'date'])
    prev = daily.groupby('symbol', sort=False).shift(1).reset_index(drop=True)
    prev_map = prev[['high', 'low', 'close']]
    piv = (prev_map['high'] + prev_map['low'] + prev_map['close']) / 3.0
    rng = (prev_map['high'] - prev_map['low']).replace(0, np.nan)
    r1 = piv + 0.382 * rng
    s1 = piv - 0.382 * rng
    r2 = piv + 0.618 * rng
    s2 = piv - 0.618 * rng

    key = list(zip(daily['symbol'], daily['date']))
    look = {k: v for k, v in zip(key, range(len(key)))}
    merge_idx = np.array([look[(s_, dt_)] for s_, dt_ in
                          zip(day_grp['symbol'], day_grp['date'])])
    prev_hi = prev_map['high'].values[merge_idx]
    prev_lo = prev_map['low'].values[merge_idx]
    drng = prev_hi - prev_lo
    drng_safe = np.where(drng == 0, np.nan, drng)

    f = pd.DataFrame(index=df.index)
    close = df['close'].values
    f['mql_pos_prev_day'] = (close - prev_lo) / drng_safe
    f['mql_dist_r1_atr'] = (close - r1.values[merge_idx]) / atr.values
    f['mql_dist_s1_atr'] = (close - s1.values[merge_idx]) / atr.values
    f['mql_dist_r2_atr'] = (close - r2.values[merge_idx]) / atr.values
    f['mql_dist_s2_atr'] = (close - s2.values[merge_idx]) / atr.values
    return f


def _zigzag(df):
    """Causal ZigZag(30, 5pt, 3): per-symbol, returns pivot price/type per bar."""
    piv_price = np.full(len(df), np.nan)
    piv_dir = np.zeros(len(df))                   # +1 high pivot, -1 low pivot
    for sym, g in df.groupby('symbol', sort=False):
        hi = g['high'].values
        lo = g['low'].values
        cl = g['close'].values
        dev = 5 * (0.01 if cl[0] > 100 else 0.0001)
        swing_extreme = -1                        # index of current extreme
        direction = 0                             # 1 hunting highs, -1 hunting lows
        for j in range(len(g)):
            if direction == 1:
                if hi[j] > hi[swing_extreme]:
                    swing_extreme = j
                elif hi[j] <= hi[swing_extreme] - dev and j - swing_extreme >= ZZ_BACKSTEP:
                    piv_price[j] = hi[swing_extreme]
                    piv_dir[j] = 1
                    direction = -1
                    swing_extreme = j
            elif direction == -1:
                if lo[j] < lo[swing_extreme]:
                    swing_extreme = j
                elif lo[j] >= lo[swing_extreme] + dev and j - swing_extreme >= ZZ_BACKSTEP:
                    piv_price[j] = lo[swing_extreme]
                    piv_dir[j] = -1
                    direction = 1
                    swing_extreme = j
            else:
                direction = 1 if cl[j] >= (hi[j] + lo[j]) / 2 else -1
                swing_extreme = j
    return (pd.Series(piv_price, index=df.index),
            pd.Series(piv_dir, index=df.index))


def zigzag_features(df, atr):
    """ZigZag swing direction + distance of close to 61.8% of last swing."""
    c = df['close']
    piv_price, piv_dir = _zigzag(df)
    n = len(df)
    dirn = np.zeros(n)
    since = np.full(n, np.nan)
    retr = np.full(n, np.nan)
    for sym, g in df.groupby('symbol', sort=False):
        s = list(g.index)
        pp = piv_price.loc[s].values
        pdv = piv_dir.loc[s].values
        cur_d, cur_pp, prev_pp = 0, np.nan, np.nan
        for j, i in enumerate(s):
            if not np.isnan(pp[j]):
                prev_pp = cur_pp
                cur_pp, cur_d = pp[j], pdv[j]
                since[j] = 0
            elif j > 0:
                since[j] = since[j - 1] + 1
            dirn[j] = cur_d
            if not np.isnan(prev_pp) and not np.isnan(cur_pp):
                sw_hi, sw_lo = max(cur_pp, prev_pp), min(cur_pp, prev_pp)
                retr[j] = sw_lo + 0.618 * (sw_hi - sw_lo)
    f = pd.DataFrame(index=df.index)
    f['mql_zz_dir'] = pd.Series(dirn, index=df.index)
    f['mql_zz_since'] = pd.Series(since, index=df.index)
    f['mql_zz_retr_618_atr'] = (c - pd.Series(retr, index=df.index)) / atr
    return f


def channel_midline_features(df, atr):
    """alex_v1_1: 8-bar high/low channel midline (prior-bar anchored)."""
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    mid = ((h.rolling(MID_WINDOW).mean() + l.rolling(MID_WINDOW).mean()) / 2).shift(1)
    side = np.sign(c.shift(1) - mid)
    cross = side != side.shift(1)
    cross_pos = cross.fillna(False).values
    last = np.where(cross_pos, np.arange(len(df)), -1)
    last = np.maximum.accumulate(last)
    since = np.where(last >= 0, np.arange(len(df)) - last, np.nan)
    f = pd.DataFrame(index=df.index)
    f['mql_ch_mid_dist_atr'] = (c - mid) / atr
    f['mql_ch_mid_cross_since'] = since * np.where(side.fillna(0).values == 0, 0, side.fillna(0).values)
    return f


def forecast_osc_features(df, atr):
    """forecast_osc-30M: T3-filtered linear-forecast oscillator + polarity."""
    c = df['close']
    slope = _rolling_slope(c, 15)
    ybar = c.rolling(15).mean()
    wt = ybar + slope * 7.5                       # one-bar-ahead linear forecast
    osc = (c - wt) / wt.replace(0, np.nan) * 100.0
    b = 0.7
    e1 = osc.ewm(alpha=b, adjust=False).mean()
    e2 = e1.ewm(alpha=b, adjust=False).mean()
    e3 = e2.ewm(alpha=b, adjust=False).mean()
    t3 = 3 * e1 - 3 * e2 + e3
    cross = ((osc > t3) & (osc.shift(1) <= t3.shift(1))).astype(int) \
        - ((osc < t3) & (osc.shift(1) >= t3.shift(1))).astype(int)
    cross_pos = cross != 0
    last = np.where(cross_pos.values, np.arange(len(df)), -1)
    last = np.maximum.accumulate(last)
    since = np.where(last >= 0, np.arange(len(df)) - last, np.nan)
    dirn = np.where(cross.fillna(0).values == 0, 0, np.sign(cross.fillna(0).values))
    f = pd.DataFrame(index=df.index)
    f['mql_fosc'] = t3
    f['mql_fosc_cross_since'] = since * dirn
    f['mql_fosc_pol'] = np.where(t3 > 0, 1, -1)
    return f


def _compute_features(df):
    """Compute all mql groups on df (no recursion, no column-list init)."""
    out = pd.DataFrame(index=df.index)
    parts_all = []
    for sym, g in df.groupby('symbol', sort=False):
        atr = _atr_safe(g['high'], g['low'], g['close'])
        if len(g) < 20:
            frame = pd.DataFrame(np.nan, index=g.index, columns=ALL_COLS)
            frame.index = g.index
            parts_all.append(frame)
            continue
        parts = [
            psar_features(g, atr),
            regime_features(g, atr),
            candle_features(g, atr),
            fractal_features(g, atr),
            outside_reversal_features(g),
            macd_ema_features(g, atr),
            fibo_pivot_features(g, atr),
            zigzag_features(g, atr),
            channel_midline_features(g, atr),
            forecast_osc_features(g, atr),
        ]
        frame = pd.concat(parts, axis=1)
        frame.index = g.index
        parts_all.append(frame)
    out = pd.concat(parts_all) if parts_all else out
    out = out.loc[df.index]
    return out[out.columns[~out.columns.duplicated()]]


def add_mql_features(df):
    """Append all mql_* features to df and return the new columns frame.

    All stateful ops (rolling, shift, ewm, PSAR, zigzag, fractal machines) are
    computed per-symbol so no feature crosses a symbol boundary.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError('df must be a DataFrame')
    if 'symbol' not in df.columns:
        df = df.assign(symbol='FX:X')
    return _compute_features(df)


def _probe_cols():
    """Canonical column order, computed once at import on a synthetic frame
    (300 bars -> the short-group branch never triggers, no recursion)."""
    probe = pd.DataFrame({
        'datetime': pd.to_datetime(pd.date_range('2024-01-01', periods=300, freq='5min')),
        'symbol': ['FX:X'] * 300,
        'open': np.linspace(1.08, 1.09, 300), 'high': np.linspace(1.0801, 1.0901, 300),
        'low': np.linspace(1.0799, 1.0899, 300), 'close': np.linspace(1.0800, 1.0900, 300),
        'volume': 1.0,
    })
    atr = _atr_safe(probe['high'], probe['low'], probe['close'])
    parts = [
        psar_features(probe, atr),
        regime_features(probe, atr),
        candle_features(probe, atr),
        fractal_features(probe, atr),
        outside_reversal_features(probe),
        macd_ema_features(probe, atr),
        fibo_pivot_features(probe, atr),
        zigzag_features(probe, atr),
        channel_midline_features(probe, atr),
        forecast_osc_features(probe, atr),
    ]
    return list(pd.concat(parts, axis=1).columns)


ALL_COLS = _probe_cols()


def mql_feature_names():
    """Feature names in the canonical order (for bundle 'features' lists)."""
    return list(ALL_COLS)
