from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# from triggerasset.views import OlympTradeTrigger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading.settings')
app = Celery('trading', broker='amqp://magesh:Magesh1@@localhost/trade')
app.conf.timezone = 'UTC'


@app.task
def start_trade():
    from triggerasset.views import OlympTradeTrigger
    client = OlympTradeTrigger()
    client.single_trigger()

app.conf.beat_schedule = {
    'run-every-minute': {
        'task': 'celery_client.start_trade',
        'schedule': crontab(minute='*')
    },
}
