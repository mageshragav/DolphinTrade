"""Retrain the ML models used by the live trading pipeline.

Reproduces the training pipeline used in the strategy notebooks
(ML_15_Min_Stradegy_1.ipynb / ML_15_Min_Stradegy_2.ipynb) but with the
fixes applied:

- lookback-only indicators (no future bars, no repainting)
- chronological data (no reversal) - identical to the runtime pipeline
- labels based on the actual next-candle direction (no label leakage)
- label horizon aligned with the trade expiry

Model names match what MLTradingPrediction.load_models expects:
    random_forest_5_min.sav      / xg_booster_5_min.sav
    random_forest_15_min.sav     / xg_booster_15_min.sav
    random_forest_15_min_2.sav   / xg_booster_15_min_2.sav
"""

import glob
import os
import pickle
import sys
import warnings

warnings.filterwarnings('ignore')

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from xgboost import XGBClassifier

CURR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURR)

from TradingStradegy.mt4stradegies import binary_arrows, super_arrows, super_signals, super_signals_v3, tm_indicator

OUTPUT_DIR = os.path.join(CURR, 'common', 'MachineLearningModel', 'output')
MODEL_DIR = os.path.join(CURR, 'common', 'ml_model')
os.makedirs(MODEL_DIR, exist_ok=True)


def signal_chain(data: pd.DataFrame, stradegy: int = 1) -> pd.DataFrame:
    """Identical to StradegyCalculation._signals in tradingasset/views.py."""
    superv3 = super_signals_v3.SuperV3SignalPredictor(data.copy()).run()
    superv2 = super_signals.SuperSignalV2Generator(superv3.reset_index(drop=True)).run()
    binary = binary_arrows.BinaryArrowSignalPredictor(superv2.reset_index(drop=True)).run()
    if stradegy == 2:
        superarrow = super_arrows.SuperArrowSignalGenerator(binary.reset_index(drop=True)).run()
        result = tm_indicator.TMIndicator(superarrow.reset_index(drop=True)).run()
    else:
        result = tm_indicator.TMIndicator(binary.reset_index(drop=True)).run()
    return result.reset_index(drop=True)


def build_dataset(csv_files, stradegy: int, horizon: int):
    """horizon = number of candles between entry open and expiry close.

    Trade enters at the open of the candle AFTER the signal candle
    (entry_open = open.shift(-1)) and expires `horizon` candles later
    (exit_close = close.shift(-(1 + horizon))).
    """
    if stradegy == 2:
        features = ['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow', 'SuperArrowSignal', 'TMSignal']
    else:
        features = ['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow', 'TMSignal']

    frames = []
    for path in csv_files:
        df = pd.read_csv(path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime').reset_index(drop=True)
        data = signal_chain(df, stradegy)
        entry_open = data['open'].shift(-1)
        exit_close = data['close'].shift(-(1 + horizon))
        all_signals_zero = (data[features] == 0).all(axis=1)
        label = pd.Series(0, index=data.index)
        label[(~all_signals_zero) & (entry_open < exit_close)] = 1
        label[(~all_signals_zero) & (entry_open > exit_close)] = 2
        frames.append(pd.DataFrame({'label': label, **{f: data[f] for f in features}}))

    dataset = pd.concat(frames, ignore_index=True)
    dataset.dropna(inplace=True)
    return dataset, features


def train_and_save(dataset, features, rf_path, xgb_path):
    X = dataset[features]
    y = dataset['label'].astype('int32')

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.35, shuffle=False)

    rf_model = RandomForestClassifier()
    rf_model.fit(X_train, y_train)
    rf_train = accuracy_score(y_train, rf_model.predict(X_train)) * 100
    rf_test = accuracy_score(y_test, rf_model.predict(X_test)) * 100

    xgb_model = XGBClassifier(booster='gbtree', max_depth=14, min_child_weight=2)
    xgb_model.fit(X_train, y_train)
    xgb_train = accuracy_score(y_train, xgb_model.predict(X_train)) * 100
    xgb_test = accuracy_score(y_test, xgb_model.predict(X_test)) * 100

    pickle.dump(rf_model, open(rf_path, 'wb'))
    pickle.dump(xgb_model, open(xgb_path, 'wb'))

    print(f'RF  train acc {rf_train:.2f}%  test acc {rf_test:.2f}%  -> {rf_path}')
    print(f'XGB train acc {xgb_train:.2f}%  test acc {xgb_test:.2f}%  -> {xgb_path}')
    print(f'label distribution: {dict(y.value_counts().sort_index())}')
    return rf_test, xgb_test


def main():
    five_min_files = sorted(
        f for f in glob.glob(os.path.join(OUTPUT_DIR, 'five_mins', '*_5_Min*.csv'))
        if 'testing' not in f
    )
    fifteen_min_files = sorted(
        f for f in glob.glob(os.path.join(OUTPUT_DIR, 'fifteen_mins', '*_15_Min*.csv'))
        if 'testing' not in f
    )
    print(f'5-min files: {len(five_min_files)}  15-min files: {len(fifteen_min_files)}')

    print('\n=== 5_min strategy (5-min candles, 5-min expiry) ===')
    ds_5, feats_5 = build_dataset(five_min_files, stradegy=1, horizon=0)
    train_and_save(ds_5, feats_5, os.path.join(MODEL_DIR, 'random_forest_5_min.sav'),
                   os.path.join(MODEL_DIR, 'xg_booster_5_min.sav'))

    print('\n=== 15_min_1 strategy (5-min candles, 15-min expiry) ===')
    ds_15_1, feats_15_1 = build_dataset(five_min_files, stradegy=1, horizon=2)
    train_and_save(ds_15_1, feats_15_1, os.path.join(MODEL_DIR, 'random_forest_15_min.sav'),
                   os.path.join(MODEL_DIR, 'xg_booster_15_min.sav'))

    print('\n=== 15_min_2 strategy (15-min candles, 15-min expiry) ===')
    ds_15_2, feats_15_2 = build_dataset(fifteen_min_files, stradegy=2, horizon=0)
    train_and_save(ds_15_2, feats_15_2, os.path.join(MODEL_DIR, 'random_forest_15_min_2.sav'),
                   os.path.join(MODEL_DIR, 'xg_booster_15_min_2.sav'))

    print('\nDone. Models saved to', MODEL_DIR)


if __name__ == '__main__':
    main()
