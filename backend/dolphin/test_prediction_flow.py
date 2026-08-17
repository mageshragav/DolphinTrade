"""Out-of-sample end-to-end test of the live prediction flow.

Simulates MLTradingPrediction.predict() exactly (same feature pipeline as
StradegyCalculation.main) on test CSVs that were NOT used for training.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pickle
import pandas as pd

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dolphin.settings')
import django
django.setup()

from TradingStradegy.views import MLTradingPrediction
from TradingStradegy.mt4stradegies import binary_arrows, super_arrows, super_signals, super_signals_v3, tm_indicator

CURR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(CURR, 'common', 'ml_model')
OUTPUT = os.path.join(CURR, 'common', 'MachineLearningModel', 'output')

FEATURES_1 = ['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow', 'TMSignal']
FEATURES_2 = ['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow', 'SuperArrowSignal', 'TMSignal']


def signal_chain(data: pd.DataFrame, stradegy: int = 1) -> pd.DataFrame:
    superv3 = super_signals_v3.SuperV3SignalPredictor(data.copy()).run()
    superv2 = super_signals.SuperSignalV2Generator(superv3.reset_index(drop=True)).run()
    binary = binary_arrows.BinaryArrowSignalPredictor(superv2.reset_index(drop=True)).run()
    if stradegy == 2:
        superarrow = super_arrows.SuperArrowSignalGenerator(binary.reset_index(drop=True)).run()
        result = tm_indicator.TMIndicator(superarrow.reset_index(drop=True)).run()
    else:
        result = tm_indicator.TMIndicator(binary.reset_index(drop=True)).run()
    return result.reset_index(drop=True)


def load_models():
    rf, xgb = {}, {}
    for key, f in [('5_min', 'random_forest_5_min.sav'), ('15_min_1', 'random_forest_15_min.sav'), ('15_min_2', 'random_forest_15_min_2.sav')]:
        rf[key] = pickle.load(open(os.path.join(MODEL_DIR, f), 'rb'))
    for key, f in [('5_min', 'xg_booster_5_min.sav'), ('15_min_1', 'xg_booster_15_min.sav'), ('15_min_2', 'xg_booster_15_min_2.sav')]:
        xgb[key] = pickle.load(open(os.path.join(MODEL_DIR, f), 'rb'))
    return rf, xgb


def run(strategy, path, timing, features, stradegy=1):
    df = pd.read_csv(path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)
    data = signal_chain(df, stradegy)

    pred = MLTradingPrediction.__new__(MLTradingPrediction)
    pred.pair = os.path.basename(path)
    pred.timing = timing
    pred.rf_models, pred.xgb_models = load_models()

    result = pred.predict(strategy, data, resouce=features)
    last = data[features].dropna()
    print(f'{os.path.basename(path):35s} [{timing:7s} {strategy:8s}] rows={len(data)} '
          f'last_features={list(last.iloc[-1])} -> prediction={result}')
    return result


print('--- 5_min models on 5-min out-of-sample data ---')
r = run('5_min', os.path.join(OUTPUT, 'five_mins', 'EURUSD_5_Min_testing.csv'), '5_MIN', FEATURES_1)
r = run('5_min', os.path.join(OUTPUT, 'five_mins', 'EURJPY_5_Min_testing_new.csv'), '5_MIN', FEATURES_1)
print()
print('--- 15_min_1 models on 5-min out-of-sample data ---')
r = run('15_min_1', os.path.join(OUTPUT, 'five_mins', 'EURUSD_5_Min_testing.csv'), '15_MIN', FEATURES_1)
r = run('15_min_1', os.path.join(OUTPUT, 'five_mins', 'AUDUSD_5_Min_testing.csv'), '15_MIN', FEATURES_1)
print()
print('--- 15_min_2 models on 15-min out-of-sample data ---')
r = run('15_min_2', os.path.join(OUTPUT, 'fifteen_mins', 'EURUSD_15_Min.csv'), '15_MIN', FEATURES_2, stradegy=2)

print()
print('OK: pipeline runs end-to-end and predictions are produced.')
