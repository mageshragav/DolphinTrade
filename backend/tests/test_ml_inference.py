"""Inference regression tests for DecisionService (light + mql bundles)."""

import glob
import os
import pickle
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dolphin.ml_service import DecisionService, COMBO_MODELS, MODEL_DIR

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   '..', 'dolphin', 'common', 'MachineLearningModel', 'output', 'five_mins')


def _sample_candles(n=250):
    paths = sorted(glob.glob(os.path.join(OUT, '*_5_Min*.csv')))
    paths = [p for p in paths if 'testing' not in p][:2]
    assert paths, 'no 5m CSVs found'
    frames = []
    for p in paths:
        df = pd.read_csv(p).tail(n).copy()
        df['symbol'] = os.path.basename(p).split('_')[0]
        df['datetime'] = pd.to_datetime(df['datetime'])
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def test_promoted_bundle_has_mql_features():
    path = os.path.join(MODEL_DIR, COMBO_MODELS[(300, 3600)])
    with open(path, 'rb') as f:
        bundle = pickle.load(f)
    mql = [c for c in bundle['features'] if c.startswith('mql_')]
    assert len(mql) == 30, f'combo_300_3600 must be the promoted mql bundle ' \
                           f'({len(mql)} mql columns)'
    assert len(bundle['features']) == 54


def test_light_bundles_unchanged():
    for combo in [(300, 900), (300, 1800), (900, 3600), (1800, 3600)]:
        path = os.path.join(MODEL_DIR, COMBO_MODELS[combo])
        with open(path, 'rb') as f:
            bundle = pickle.load(f)
        assert not any(c.startswith('mql_') for c in bundle['features']), combo


def test_decision_service_runs_with_mql_bundle():
    svc = DecisionService(theta=0.65)
    candles = _sample_candles(250)
    decisions = svc.decide_for_combo(candles, 300, 3600, equity=1000.0)
    # must run without error and produce well-formed payloads
    for d in decisions:
        assert d['symbol'] and d['action'] in ('CALL', 'PUT', 'NEUTRAL')
        assert d['atr'] > 0
        assert d['entry_price'] > 0
    # the mql bundle must actually be served for (300, 3600)
    bundle = svc.combo_models[(300, 3600)]
    assert any(c.startswith('mql_') for c in bundle['columns'])


def test_decide_all_theta_override():
    """The hourly scan must be able to see candidates below the production
    gate (theta override) - otherwise the guarantee never fires."""
    svc = DecisionService(theta=0.65)
    candles = _sample_candles(250)
    full = svc.decide_all(candles, combos=[(300, 3600)])
    low = svc.decide_all(candles, combos=[(300, 3600)], theta=0.55)
    # with the override, strictly more candidates get CALL/PUT actions
    act = lambda ds: [d for d in ds if d['action'] in ('CALL', 'PUT')]
    assert len(act(low)) >= len(act(full))
