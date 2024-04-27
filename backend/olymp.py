# from dolphin.common.apiconnection.olymptradeapi import OlympTradeAPI
# from dolphin.common.constants import HEADERS,OLYMP_WS
# from datetime import datetime

# s = OlympTradeAPI()
# date_time = datetime.now()
# print(s.get_profit_lose_analysis(date_time))
from websocket import create_connection
import time, random, string, json, requests, datetime, threading

class Client():
    def __init__(self, session):
        self.headers = {'Cookie': session, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36'}
        self.host_v6 = r"wss://ws.olymptrade.com/otp?cid_ver=1&cid_app=web%40OlympTrade%402023.3.20364%4020364&cid_device=%40%40desktop&cid_os=linux%40x86_64"
        self.parsedCurrency = {}
        # for wallet in self.getWallet():
        #     print("Balance: "+str(wallet["amount"])+"USD")
        #     opt = input("Y/N? ")
        #     if opt.lower() == "y":self.accountId = str(wallet["account_id"]);self.accountGroup = wallet["group"];break
        # self.updateCurrency()

    def generateUuid(self,size=18):
        if size !=6:
            return ''.join([random.choice(string.ascii_uppercase+string.digits) for n in range(size)])
        return ''.join([random.choice(string.ascii_uppercase+string.ascii_lowercase) for n in range(size)])

    def getBet(self, status, pair, amount="1", duration="60"):
        ws = create_connection(self.host_v6,header=self.headers)
        ws.send('[{"t":2,"e":23,"uuid":"'+self.generateUuid()+'","d":[{"amount":'+amount+',"dir":"'+status+'","pair":"'+pair+'","cat":"'+self.parsedCurrency[pair]+'","pos":0,"source":"platform","account_id":'+self.accountId+',"group":"'+self.accountGroup+'","timestamp":'+str(int(time.time()))+',"risk_free_id":null,"duration":'+duration+'}]}]')
        data =  json.loads(ws.recv())
        ws.close()
        return data[0]["d"][0]

    def getWallet(self):
        ws = create_connection(self.host_v6,header=self.headers)
        ws.send('[{"t":2,"e":98,"uuid":"'+self.generateUuid()+'","d":[54]}]')
        data = json.loads(ws.recv())
        ws.close()
        return data[0]["d"]

    def getBalance(self):
        data = self.getWallet()
        return [i["amount"] for i in data if str(i["account_id"]) == self.accountId][0]

    def getOngoingBet(self):
        ws = create_connection(self.host_v6,header=self.headers)
        ws.send('[{"t":2,"e":31,"uuid":"'+self.generateUuid()+'","d":[{"account_id":'+self.accountId+',"group":"'+self.accountGroup+'"}]}]')
        data =  json.loads(ws.recv())[0]["d"]
        ws.close()
        return data

    def getCurrency(self):
        ws = create_connection(self.host_v6,header=self.headers)
        ws.send('[{"t":2,"e":98,"uuid":"'+self.generateUuid()+'","d":[70]}]')
        ws.recv()
        data = json.loads(ws.recv())[0]["d"]
        ws.close()
        return data
    
    def getcandle(self):
        ws = create_connection(self.host_v6,header=self.headers)
        ws.send('[{"t":2,"e":10,"uuid":"'+self.generateUuid(size=6)+'","d":[{"pair":"EURUSD_OTC","size":60,"to":1714205200,"solid":true}]}]')
        data = json.loads(ws.recv())[0]["d"]
        ws.close()
        return data

    def getHistory(self):
        headers = {**self.headers.copy(), **{'X-App-Version': '7673', 'X-Request-Project': 'bo', 'X-Request-Type': 'Api-Request', 'X-Requested-With': 'XMLHttpRequest'}}
        data = {"limit": 10, "group": self.accountGroup, "order": "time_close", "page": 1, "account_id": int(self.accountId)}
        return requests.post("https://api.olymptrade.com/v3/cabinet/deals-history",headers=headers,json=data).json()

    def updateCurrency(self):
        ws = create_connection(self.host_v6,header=self.headers)
        ws.send('[{"t":2,"e":98,"uuid":"'+self.generateUuid()+'","d":[70]}]')
        ws.recv()
        data = json.loads(ws.recv())[0]["d"]
        ws.close()
        for i in data:self.parsedCurrency[i["name"]] = i["group"]


cookies = {
    'access_token': 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3MTQzNzc2NTUsImlhdCI6MTcxNDIwNDg1NSwiaWQiOjM4MTEyNTU2NSwibmJmIjoxNzE0MjA0ODU1LCJyZXFfY3R4X2hhc2giOiIzNzBiNTFlYWI5ZmMzYmUxMzZiNjRjYzA3MTI2YzY1NCIsInR5cGUiOiJiZWFyZXIiLCJ1c2VyX2lkIjo0NjMwMDA4NH0.Odvr0g7hzmn452lUQMd3HaCGeUIdu3_8PDR4Vfn-49PHt-dxtFvurauNF454064Fiqw3f8Jnw-JPn3wx_kG1WfjG-jHjqt7oXgEQlcv21zdjXQSik6k2XVIfnVXoZGTQpNmRpQ35gevgFSD0UZY-zsW6V-wJC1LhvSeRr0KdK-rRp1RezY0M4nAUlc3OpNiL98CkIEG0dHZv6mEQWJEUfrmI_4rnFiPgefXef5l4M-s2XH7o8cYo2zWvPcijCMIXA2hFc2TJ5N4VUfP2ZX-BT2zLAzXJKa0fsxMlgH_1b8YV_VFgdCrY65Hclwpk81wCPdu3PQEnUeRA0lf19UU14_habhpViDQb5zG89Fdv0vUssV4SNLO8AxcvDjoXAt1t0RD8a94erj5AbLDRr1z7hMWPfViFrdg322tnTngSYMbKN7QRHDidYPx0MqcMHDQkqVCsk7Y9dQkjxbp3HKxkpcvJJ2NXNucAVR6YAG-fR2nGGKX8ixIdy3qroWhcI-ZAV5xZdqcmycbyUiqUSdZYbDofYDGAkcYD_YRBqOwKWZgDRUatoRMgyWZBW08xBnES5drLGP9BKkOptMv54QeajvCTDo-k_0Qul0NpS_c45izTESxKVGrqil5juV8X0bmaNiiPbZh-TpXOxwC5vUqrz1tuWV1_j7t4AueYl6_EYB4',
    'jwt_auth': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3MTQyMDQ4NTgsIm5iZiI6MTcxNDIwNDg1OCwiZXhwIjoxNzE0MjkxMjU4LCJ1c2VyX2lkIjo0NjMwMDA4NCwiZW1haWwiOiJtYWdlc2htZ3IxQGdtYWlsLmNvbSJ9.G2xDowEWJL5_H_wBALI_gJp7B_ERimIRWDt0ONoRALXCxhiLaEX8M8pZBI2SXpjIeU2vLU0rTWegSAWKGv9qO89ACByw9lBvRf8MmiiBHVhJiWuiYFgDKPxu-VPm9qRJoVPBaGJJJ3qFcO7Nkd1MRCYQt1BNX43O9ZY6pYUl2DdsgmbYFU0hDElJljZbiuk2cIgvuNg_gs8iUqL_JvMXs2a2vWHIkZUC-yqxQPuXCeKt_mL0isENltkr5k7YxUW2AVND9EpYo0srzczsvXbNgINyE040IxfUXrwGVzVbpdKw73W6ZcMN28VOCsYKZ_tEyypS5TjFyZborsr5RGMM_2ISDwMuHvj6iJYNiW7PvpQJa7GE-QzJI3F6lp51zLtpGHBRY6eiK-AHH5ol7o7r0S95auQJbnznoljKuOKNCzGp9mweeY-gS7-zzSydMT5aLZIfuFYlULCbHhntGwD37BtaCv0i36h0Dh1z4-LrpnOIKXgkyuoVNtDx2gDwcS7NsWPgSOW4O6MO-8d8mn7oIsmczhADtG34wVFT8qZlLwhllfOvNHYZt-Kw5IryVtKewVyIBtBk8wPd8dNP4fK-Dr0GECAa8b8QrvzjqrU7STBAIcrXCngcc1Th8ekZm0ST3QxYYU1hVtenha5W6w9hQLiwvmfIR8ycj08mUdqTfCA',
}  
cookies_str = '; '.join([f"{key}={value}" for key, value in cookies.items()])

c = Client(session=cookies_str)
print('connected!!!')
c.getcandle()