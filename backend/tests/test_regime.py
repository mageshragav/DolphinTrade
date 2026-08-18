"""Regime classifier tests: trend/range/high-vol/unknown + theta modulation.

Run:  cd backend && python -m pytest tests/test_regime.py -q
"""

import sys
import os
from datetime import datetime, timedelta, timezone

import math
import pandas as pd
import pytest

os.environ['DT_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['DT_DRY_RUN'] = 'true'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import regime  # noqa: E402


def _frame(price_fn, n=200, atr_width=0.0010):
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        p = price_fn(i)
        rows.append({'symbol': 'FX:EURUSD', 'datetime': base + timedelta(minutes=5 * i),
                     'open': p, 'high': p + atr_width, 'low': p - atr_width,
                     'close': p + 0.0001, 'volume': 100 + i})
    return pd.DataFrame(rows)


def test_trend_regime_relaxes_theta():
    # strong monotonic trend: fast EMA far from slow EMA
    candles = _frame(lambda i: 1.0 + i * 0.0004)
    r = regime.classify(candles)
    assert r['regime'] in ('trend', 'high_vol')
    assert r['theta_delta'] <= 0.0
    assert regime.effective_theta(0.65, r['theta_delta']) <= 0.65


def test_range_regime_raises_theta():
    # flat sine with tiny amplitude: mean reversion, chop
    candles = _frame(lambda i: 1.0 + math.sin(i / 5.0) * 0.0002)
    r = regime.classify(candles)
    assert r['regime'] == 'range'
    assert r['theta_delta'] > 0.0
    assert regime.effective_theta(0.65, r['theta_delta']) > 0.65


def test_high_vol_regime():
    # big ATR spikes near the end (last bars far above the 50-bar mean)
    def price(i):
        base = 1.0 + math.sin(i / 5.0) * 0.0002
        if i >= 180:
            base += (i - 180) * 0.02      # huge late moves
        return base
    candles = _frame(price, atr_width=0.004)
    r = regime.classify(candles)
    assert r['regime'] == 'high_vol'
    assert r['theta_delta'] >= 0.05


def test_theta_clamped():
    assert regime.effective_theta(0.65, +0.5) == regime.THETA_MAX
    assert regime.effective_theta(0.65, -0.5) == regime.THETA_MIN


def test_empty_frame_unknown():
    r = regime.classify(pd.DataFrame())
    assert r['regime'] == 'unknown'
    assert r['theta_delta'] == 0.0
    r2 = regime.classify(None)
    assert r2['regime'] == 'unknown'


def test_live_wire_format_accepted():
    """The feed hands the raw broker frame (t/o/h/l/c/v) - classify must
    normalise it before computing indicators."""
    import numpy as np
    base = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(150):
        p = 1.0 + i * 0.0004
        rows.append({'symbol': 'FX:EURUSD',
                     't': int(base.timestamp()) + i * 300,
                     'o': p, 'h': p + 0.001, 'l': p - 0.001, 'c': p + 0.0001,
                     'v': 100 + i})
    r = regime.classify(pd.DataFrame(rows))
    assert r['regime'] in ('trend', 'high_vol', 'mixed', 'range')
    assert 'FX:EURUSD' in r['detail']