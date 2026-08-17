"""Lookahead-safety tests for the MQL-derived feature module.

Core guarantee: feature row k computed on the FULL frame must equal feature
row k computed on the frame truncated at row k (no future-bar leakage).
This is the same leak class that faked the 92-96% results in super_arrows.
"""

import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dolphin.features.mql_signals import add_mql_features, mql_feature_names

MQL_COLS = None


def _make_frame(n=600, seed=7):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, 0.0008, n)
    close = 1.08 * np.exp(np.cumsum(rets))
    o = close * (1 + rng.normal(0, 0.0002, n))
    h = np.maximum(o, close) * (1 + np.abs(rng.normal(0, 0.0004, n)))
    l = np.minimum(o, close) * (1 - np.abs(rng.normal(0, 0.0004, n)))
    ts = pd.date_range('2024-01-01', periods=n, freq='5min')
    return pd.DataFrame({
        'datetime': ts, 'symbol': ['FX:EURUSD'] * n,
        'open': o, 'high': h, 'low': l, 'close': close, 'volume': rng.integers(50, 500, n),
    })


def _make_multi_frame(seed=3, n=800):
    f = _make_frame(n, seed)
    f2 = f.copy()
    f2['datetime'] = pd.date_range('2024-03-01', periods=len(f), freq='5min')
    f2['symbol'] = 'FX:EURJPY'
    f2['close'] = f2['close'] * 150
    f2['open'] = f2['open'] * 150
    f2['high'] = f2['high'] * 150
    f2['low'] = f2['low'] * 150
    return pd.concat([f, f2], ignore_index=True)


@pytest.fixture(autouse=True, scope='module')
def _cols():
    global MQL_COLS
    MQL_COLS = mql_feature_names()


def _assert_same(a, b):
    a_nan = np.isnan(a)
    b_nan = np.isnan(b)
    assert (a_nan == b_nan).all(), f'NaN pattern differs (nan: {a_nan.sum()} vs {b_nan.sum()})'
    assert np.allclose(a[~a_nan], b[~a_nan], rtol=1e-9, atol=1e-9)


def test_feature_count_and_names():
    assert len(MQL_COLS) == 30, f'expected 30 mql features, got {len(MQL_COLS)}: {MQL_COLS}'
    assert all(c.startswith('mql_') for c in MQL_COLS)
    assert len(set(MQL_COLS)) == len(MQL_COLS)


def test_lookahead_truncation_invariance():
    """Feature row k must be identical whether computed on full or truncated data."""
    df = _make_frame(600)
    f_full = add_mql_features(df)
    for k in [100, 200, 350, 500]:
        prefix = df.iloc[:k + 1].reset_index(drop=True)
        f_pre = add_mql_features(prefix)
        for col in MQL_COLS:
            _assert_same(f_full[col].iloc[k], f_pre[col].iloc[k])
    # also on a multi-symbol frame
    df2 = _make_multi_frame()
    f2_full = add_mql_features(df2)
    for k in [120, 260]:
        prefix = df2.iloc[:k + 1].reset_index(drop=True)
        f2_pre = add_mql_features(prefix)
        for col in MQL_COLS:
            _assert_same(f2_full[col].iloc[k], f2_pre[col].iloc[k])


def test_symbol_isolation():
    """Stateful features must not leak across symbols."""
    df = _make_multi_frame()
    f = add_mql_features(df)
    eurusd = df[df['symbol'] == 'FX:EURUSD']
    first_jpy = df.index[df['symbol'] == 'FX:EURJPY'].min()
    jpy = df.iloc[first_jpy:]
    f_jpy = add_mql_features(jpy.reset_index(drop=True))
    # features inside the second symbol must match those computed on it alone
    for col in MQL_COLS:
        for k in [50, 200]:
            _assert_same(f[col].iloc[first_jpy + k], f_jpy[col].iloc[k])
    # fibo pivots must actually resolve (they are NaN-free on day >= 2)
    assert f['mql_pos_prev_day'].isna().mean() < 0.5


def test_offset_label_slices():
    """Symbol slices with offset index labels must not misalign (regression:
    fibo-pivot features were silently all-NaN when the second symbol's slice
    started at a nonzero label)."""
    df = _make_multi_frame()
    f = add_mql_features(df)
    sym2 = df[df['symbol'] == 'FX:EURJPY']
    f_alone = add_mql_features(sym2.reset_index(drop=True))
    off = f.loc[sym2.index].reset_index(drop=True)
    for col in MQL_COLS:
        _assert_same(off[col].values, f_alone[col].values)


def test_signal_sanity():
    """Pattern counts are bounded and directional features take expected values."""
    df = _make_frame(600)
    f = add_mql_features(df)
    assert f['mql_pat_bull3'].max() <= 3
    assert f['mql_pat_bear3'].max() <= 3
    assert set(pd.unique(f['mql_macd_state'].dropna())) <= {0, 1, -1}
    assert set(pd.unique(f['mql_zz_dir'].dropna())) <= {0, 1, -1}
    assert set(pd.unique(f['mql_fosc_pol'].dropna())) <= {1, -1}
    assert set(pd.unique(f['mql_outrev_bull'].dropna())) <= {0, 1}
    assert set(pd.unique(f['mql_outrev_bear'].dropna())) <= {0, 1}


def test_real_data_runs():
    """The module must run on a real research CSV without error."""
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', 'dolphin', 'common', 'MachineLearningModel', 'output', 'fifteen_mins')
    import glob
    paths = sorted(glob.glob(os.path.join(out, '*.csv')))[:3]
    if not paths:
        pytest.skip('no research CSVs found')
    for p in paths:
        raw = pd.read_csv(p)
        raw['symbol'] = os.path.basename(p).split('_')[0]
        raw['datetime'] = pd.to_datetime(raw['datetime'])
        raw = raw.sort_values('datetime').reset_index(drop=True)
        f = add_mql_features(raw)
        assert len(f) == len(raw)
        assert f.isna().mean().max() < 0.9, f'feature mostly NaN on {p}'
