from common.socketconnect.Olymptradeconnect import OlympTradeClient
from dolphin.celery import app

olymp_client = OlympTradeClient(group='demo')

@app.task('bet_call')
def bet_call(dir='up',symbols='EURUSD',amount='1',duration='300'):
    response_data = olymp_client.get_bet(dir,symbols,amount,duration)
    print(response_data)