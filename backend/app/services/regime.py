"""Market regime classification + theta modulation.

Regimes (computed per symbol, aggregated across the watchlist):
  trend     - fast EMA is far from the slow EMA (in ATRs) -> edge is clearer,
              theta can relax slightly
  range     - price hugging the mean -> chop, raise the gate
  high_vol  - ATR running well above its own 50-bar average -> spike risk,
              raise the gate harder
  mixed     - no dominant read -> leave the configured theta alone

The runtime applies theta_delta to the configured gate each cycle and
broadcasts regime changes so the operator can see WHY the gate moved.
"""

import logging

import numpy as np
import pandas as pd
import ta

LOGGER = logging.getLogger('dolphin')

THETA_MIN = 0.50
THETA_MAX = 0.80


def classify(candles: pd.DataFrame | None) -> dict:
    """Classify the current regime over the candle watchlist.

    Returns {'regime', 'theta_delta', 'avg_trend', 'avg_vol', 'detail'}.
    """
    if candles is None or getattr(candles, 'empty', True):
        return {'regime': 'unknown', 'theta_delta': 0.0, 'avg_trend': 0.0,
                'avg_vol': 0.0, 'detail': {}}
    df = candles.copy()
    if 'o' in df.columns and 'open' not in df.columns:
        df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low',
                                'c': 'close', 'v': 'volume'})
    if 'datetime' not in df.columns and 't' in df.columns:
        df['datetime'] = pd.to_datetime(df['t'], unit='s', utc=True)
    df['datetime'] = pd.to_datetime(df['datetime'])
    if df['datetime'].dt.tz is not None:
        df['datetime'] = df['datetime'].dt.tz_localize(None)
    detail = {}
    for sym, g in df.groupby('symbol'):
        g = g.sort_values('datetime')
        if len(g) < 30:
            continue
        close, high, low = g['close'], g['high'], g['low']
        atr = ta.volatility.average_true_range(high, low, close, window=14)
        atr_safe = atr.replace(0, np.nan)
        ema_f = close.ewm(span=9).mean()
        ema_s = close.ewm(span=21).mean()
        trend = float((((ema_f - ema_s).abs() / atr_safe).iloc[-1]) or 0.0)
        atr_base = atr.rolling(50).mean()
        vol_ratio = float((atr.iloc[-1] / atr_base.iloc[-1]) if len(g) >= 50
                          and not np.isnan(atr_base.iloc[-1]) and atr_base.iloc[-1] > 0
                          else 1.0)
        atr_frac = float((atr_safe.iloc[-1] / close.iloc[-1]) or 0.0)
        detail[sym] = {'trend': round(trend, 3), 'vol_ratio': round(vol_ratio, 3),
                       'atr_frac': round(atr_frac, 6)}
    if not detail:
        return {'regime': 'unknown', 'theta_delta': 0.0, 'avg_trend': 0.0,
                'avg_vol': 0.0, 'detail': {}}
    avg_trend = float(np.mean([v['trend'] for v in detail.values()]))
    avg_vol = float(np.mean([v['vol_ratio'] for v in detail.values()]))
    if avg_vol >= 1.8:
        regime, delta = 'high_vol', +0.05
    elif avg_trend >= 0.6:
        regime, delta = 'trend', -0.02
    elif avg_trend <= 0.25:
        regime, delta = 'range', +0.03
    else:
        regime, delta = 'mixed', 0.0
    return {'regime': regime, 'theta_delta': delta,
            'avg_trend': round(avg_trend, 3), 'avg_vol': round(avg_vol, 3),
            'detail': detail}


def effective_theta(configured: float, delta: float) -> float:
    return min(THETA_MAX, max(THETA_MIN, configured + delta))