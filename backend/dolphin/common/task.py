from TradingStradegy.views import MLTradingPrediction
from common.constants import *
from datetime import *
from common.telegram_bot import send_telegram_message
from dolphin.celery import app as ap
from django.conf import settings
import logging

LOGGER = logging.getLogger('dolphin')
curr_dir = settings.BASE_DIR

@ap.task
def callorput(assest: str):
    try:  
        assest =assest #+ '_OTC'
        time_ = '15_MIN'
        prediction = MLTradingPrediction(pair=assest, timing=time_)
        result = prediction.place_order(amount=10)
        if result == 1:
            msg = f'{assest} for next {time_} will be BUY'
            send_telegram_message.apply_async(args=(f"{curr_dir}{IMAGE_GREEN}", msg))
        elif result == 2:
            msg = f'{assest} for next {time_} will be SELL'
            send_telegram_message.apply_async(args=(f"{curr_dir}{IMAGE_RED}", msg))
        else:
            LOGGER.info('NEUTRAL')
    except Exception as e:
        LOGGER.exception(f'callorput failed for {assest}: {e.args}')