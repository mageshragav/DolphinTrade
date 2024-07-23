from django.conf import settings
import pickle
from tradingasset.models import OlympTrade
from tradingasset.views import OlympTradeTrigger
from datetime import timedelta, datetime
import logging

LOGGER = logging.getLogger('dolphin')
CURR_DIR = settings.BASE_DIR

class MLTradingPrediction:
    
    def __init__(self, pair='EURUSD', timing='5_MIN') -> None:
        self.client = OlympTradeTrigger()
        self.timing = timing
        self.pair = pair
        self.model_paths = {
            'rf': {
                '5_min': 'random_forest_5_min.sav',
                '15_min_1': 'random_forest_15_min.sav',
                '15_min_2': 'random_forest_15_min_2.sav'
            },
            'xgb': {
                '5_min': 'xg_booster_5_min.sav',
                '15_min_1': 'xg_booster_15_min.sav',
                '15_min_2': 'xg_booster_15_min_2.sav'
            }
        }
        self.rf_models = self.load_models(self.model_paths['rf'])
        self.xgb_models = self.load_models(self.model_paths['xgb'])
        self.five_min_data = self.get_candle_data(self.pair, 300) # 5 min in seconds
        self.fifteen_min_data = self.get_candle_data(self.pair, 900) # 15 min in seconds

    def load_models(self, paths):
        models = {}
        for key, path in paths.items():
            try:
                models[key] = pickle.load(open(f'{CURR_DIR}/common/ml_model/{path}', 'rb'))
            except FileNotFoundError:
                models[key] = None
                print(f"Model file {path} not found.")
        return models

    def get_candle_data(self, pair='EURUSD', size=300):
        return self.client.get_candles(pair=pair, size=size)

    def apply_mt_4_algorithms(self, df):
        return self.client.calculate_1(df)

    def predict(self, strategy, input_data):
        rf_model = self.rf_models.get(strategy)
        xgb_model = self.xgb_models.get(strategy)

        if not rf_model or not xgb_model:
            return 0

        rf_result = rf_model.predict(input_data).iloc[-1]
        xgb_result = xgb_model.predict(input_data).iloc[-1]
        LOGGER.info(f'rf result {rf_result} and xgb result {xgb_result} currency on {self.pair} and timing {self.timing}')
        if rf_result == 1 and xgb_result == 1:
            return 1
        elif rf_result == 2 and xgb_result == 2:
            return 2
        else:
            return 0

    def place_order(self, amount='1'):
        timing_seconds = 300 if self.timing == '5_MIN' else 900
        prediction_function = self.five_min_strategy_5_min_chart if self.timing == '5_MIN' else self.fifteen_min_strategy_5_min_chart
        prediction = prediction_function()
        prediction_2 = 0
        if self.timing == '15_MIN':
            prediction_2 = self.fifteen_min_strategy_15_min_chart()

        if prediction in [1, 2] and prediction_2 in [1, 2]:
            if not OlympTrade.objects.filter(asset=self.pair, created_at__gte=datetime.now()-timedelta(seconds=timing_seconds)).exists():
                OlympTrade.objects.create(asset=self.pair, created_at=datetime.now())
                direction = 'up' if prediction == 1 else 'down'
                self.client.olymp_client.get_bet(direction, self.pair, amount=amount, duration=str(timing_seconds))
                self.client.olymp_client.disconnect()
                return prediction
        self.client.olymp_client.disconnect()
        return 0

    def five_min_strategy_5_min_chart(self):
        strategy_resource = ['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow', 'TMSignal']
        data = self.apply_mt_4_algorithms(self.five_min_data)[strategy_resource]
        return self.predict('5_min', data)

    def fifteen_min_strategy_5_min_chart(self):
        strategy_resource = ['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow', 'TMSignal']
        data = self.apply_mt_4_algorithms(self.fifteen_min_data)[strategy_resource]
        return self.predict('15_min_1', data)

    def fifteen_min_strategy_15_min_chart(self):
        strategy_resource = ['SuperSignalV3', 'SuperSignalV2', 'BinaryArrow', 'SuperArrowSignal', 'TMSignal']
        data = self.apply_mt_4_algorithms(self.fifteen_min_data)[strategy_resource]
        return self.predict('15_min_2', data)
