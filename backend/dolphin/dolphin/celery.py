from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
import requests
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from django.utils import timezone
from datetime import timedelta, datetime
from celery.schedules import schedule



os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dolphin.settings')
app = Celery('dolphin', broker='amqp://magesh:Magesh1@@localhost/trade')
app.conf.timezone = 'UTC'


@app.task
def start_trade():
    response = requests.get("http://localhost:8001/signal/")
    print(response.status_code)
    print(response.json())
    # sheet_update.apply_async(args=[response.json()])

@app.task(task_name='sheet_update')
def sheet_update(response=None):
    import json
    try:
        scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
        ]
        credentials = ServiceAccountCredentials.from_json_keyfile_name('google-credentials.json', scopes)
        gc = gspread.authorize(credentials)
        sheet = gc.open_by_url('https://docs.google.com/spreadsheets/d/10_56aiY13RWM0abBk8Zq4JxNYkdlpzsom0FkZolZh3Q/edit?usp=sharing').worksheet('Sheet13')
        headers = ['DATE AND TIME', 'ASSET NAME', 'RECOMMENDATION', 'BUY', 'SELL','NEUTRAL', 'TOTAL']  # Replace with your actual field names
        first_row_values = sheet.row_values(1)
        if first_row_values != headers:
            sheet.insert_row(headers, 1)
        data = []
        for obj in response:
            if obj['personal']['BUY'] or obj['personal']['SELL']:
                five_min = timezone.now()-timedelta(minutes=5)
                # if not OlympTrade.objects.filter(asset=obj['asset'], created_at__range=[five_min,timezone.now()]).exists():
                data.append([obj['date_time'],obj['asset'],obj['RECOMMENDATION'],
                            obj['BUY'], obj['SELL'], obj['NEUTRAL'], str(json.loads(obj['TOTAL']))
                            ])
        data.append(['########','########','########','########','########','########','########'])
        sheet.append_rows(data)

        return True
    except Exception as e:
        print(e.args)
        return False


@app.task
def update():
    response = requests.get("http://localhost:8001/generate-data/")
    print(response.status_code)
    print(response.json())
    
app.conf.beat_schedule = {
    'run-every-minute': {
        'task': 'dolphin.celery.start_trade',
        'schedule': crontab("*", "*", "*", "*", "*")
    },
    # 'run-every-5-minute': {
    #     'task': 'dolphin.celery.update',
    #     'schedule': crontab(minute='*')
    # },
}
