import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
credentials = ServiceAccountCredentials.from_json_keyfile_name('google-credentials.json', scopes)
gc = gspread.authorize(credentials)
sheet = gc.open_by_url('https://docs.google.com/spreadsheets/d/1YORJxDeuzHkuudH-rFYlyaK4IdJ-f_liqR_2apQUIBI/edit?usp=drive_link').sheet1
headers = ['DATE AND TIME', 'ASSET NAME', 'RECOMMENDATION', 'BUY', 'SELL','NEUTRAL', 'Personal.BUY', 'Personal.SELL', 'RSI', 'MACD']  # Replace with your actual field names
sheet.insert_row(headers, 1)
response = requests.get("http://localhost:8001/signal/")
print(response.status_code)
data = []
for obj in response.json():
    data.append([obj['date_time'],obj['asset'],obj['RECOMMENDATION'],
                 obj['BUY'], obj['SELL'], obj['NEUTRAL'], obj['personal']['BUY'],
                 obj['personal']['SELL'], obj['RSI'], obj['MACD']
                ])
sheet.append_rows(data)
