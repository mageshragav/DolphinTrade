from tradingview_ta import TA_Handler, Interval, Exchange, get_multiple_analysis

class TradingViewApi:
    def __init__(self,symbols,screener,exchange,interval) -> None:
        self.symbols = symbols
        self.screener = screener
        self.exchange = exchange
        self.interval = interval
        self.signal = self.signal_data() if isinstance(symbols,str) else self.multi_data()

    def signal_data(self):
        data = TA_Handler(
            symbol=self.symbols,
            screener=self.screener,
            exchange=self.exchange,
            interval=self.interval
        )
        # <tradingview_ta.main.Analysis object at 0x7f3561cdeb20>
        return data

    def multi_data(self):
        data = get_multiple_analysis(
            symbol=self.symbols,
            screener=self.screener,
            exchange=self.exchange,
            interval=self.interval
        )
        # {'BINANCE:DEXEUSDT': None, 'BINANCE:BTCUSDT': <tradingview_ta.main.Analysis object at 0x7f3561cdeb20>}
        return data

    def analysis(self,signal):
        return signal.get_analysis()
    
    def get_summary(self,signal):
        summary = self.analysis(signal).summary
        # {'RECOMMENDATION': 'BUY', 'BUY': 12, 'SELL': 7, 'NEUTRAL': 9}
        return summary
    
    def get_indicators(self,signal):
        indicators = self.analysis(signal).indicators
        return indicators

    def get_oscillators(self,signal):
        oscillators = self.analysis(signal).oscillators
        # {'RECOMMENDATION': 'BUY', 'BUY': 2, 'SELL': 1, 'NEUTRAL': 8, 
        # 'COMPUTE': {'RSI': 'NEUTRAL', 'STOCH.K': 'NEUTRAL', 'CCI': 'NEUTRAL',
        # 'ADX': 'NEUTRAL', 'AO': 'NEUTRAL', 'Mom': 'BUY', 'MACD': 'SELL',
        # 'Stoch.RSI': 'NEUTRAL', 'W%R': 'NEUTRAL', 'BBP': 'BUY', 'UO': 'NEUTRAL'}}
        return oscillators
    
    def get_moving_avg(self,signal):
        mv = self.analysis(signal).moving_averages
        #{'RECOMMENDATION': 'BUY', 'BUY': 9, 'SELL': 5, 'NEUTRAL': 1, 
        # 'COMPUTE': {'SMA5': 'SELL', 'SMA10': 'SELL', 'EMA20': 'SELL',
        # 'SMA20': 'SELL', 'EMA30': 'BUY', 'SMA30': 'BUY', 'EMA50': 'BUY',
        # 'SMA50': 'BUY', 'SMA50': 'BUY', 'SMA100': 'BUY', 'EMA200': 'BUY',
        # 'SMA200': 'BUY', 'Ichimoku': 'NEUTRAL', 'VWMA': 'SELL', 'HullMA': 'BUY'}}
        return mv
    
    def personal_recommendation(self,data, oscillator, indicator, mv):
        RSI = oscillator['COMPUTE']['RSI']
        IRSI = indicator['RSI']
        IRSI1 = indicator['RSI[1]']
        MCAD = oscillator['COMPUTE']['MACD']
        MOM = oscillator['COMPUTE']['Mom']
        BBP = oscillator['COMPUTE']['BBP']
        CCI = indicator['CCI20']
        WR = oscillator['COMPUTE']['W%R']
        WRR = indicator['W.R']
        HullMA = mv['COMPUTE']['HullMA']
        STOCHK = oscillator['COMPUTE']['STOCH.K']
        STOCHRSI = oscillator['COMPUTE']['Stoch.RSI']
        SMA100 = mv['COMPUTE']['SMA100']
        SMA200 = mv['COMPUTE']['SMA200']
        EMA100 = mv['COMPUTE']['EMA100']
        EMA200 = mv['COMPUTE']['EMA200']
        EMA5 = 'SELL' if indicator['EMA5'] > indicator['close'] else 'BUY'
        SMA5 = 'SELL' if indicator['SMA5'] > indicator['close'] else 'BUY'
        EMAS = [SMA100,SMA200,EMA100,EMA200]
        print(f"-------********{data['asset']}********------------")
        print(f"MCAD: {MCAD},\nMOM: {MOM},\nRSI: {RSI},\nWRR: {WRR},\nEMA5: {EMA5},\nSMA5: {SMA5},\nHullMA: {HullMA},\nIRSI: {IRSI},\nIRSI1: {IRSI1}")
        print(f"oscillator: {oscillator['RECOMMENDATION']},\nmoving avg: {mv['RECOMMENDATION']}")
        print(f"-------********{data['asset']}********------------")
        # if int(IRSI) == int(IRSI1):
        #     print(f"{data['asset']} returning false because of rsi warning")
        #     return {'BUY':False,'SELL':False}
        if MCAD in 'BUY' and MOM in 'BUY' and RSI in ('NEUTRAL', 'BUY'):
            if mv['RECOMMENDATION'] in ('BUY', 'STRONG_BUY') and oscillator['RECOMMENDATION'] in 'BUY':
                if (EMA5 in 'BUY' and SMA5 in 'BUY') and HullMA == 'BUY':
                    if WRR < -80 and IRSI > IRSI1:
                        print(f"{data['asset']} returning true because of wrr implement")
                        return {'BUY':False,'SELL':True}
                    elif WRR > -20 and IRSI < IRSI1:
                        print(f"{data['asset']} returning true because of rsi implement")
                        return {'BUY':True,'SELL':False}
                    # elif WRR < -75 and IRSI > IRSI1:
                    #     print(f"{data['asset']} returning true because of wrr implement")
                        return {'BUY':False,'SELL':True}
        elif MCAD in 'SELL' and MOM in 'SELL' and RSI in ('NEUTRAL', 'SELL'):
            if mv['RECOMMENDATION'] in ('SELL', 'STRONG_SELL') and oscillator['RECOMMENDATION'] in 'SELL':
                if (EMA5 in 'SELL' and SMA5 in 'SELL') and HullMA == 'SELL':
                    if WRR > -20 and IRSI < IRSI1:
                        print(f"{data['asset']} returning true because of wrr implement")
                        return {'BUY':True,'SELL':False}
                    elif WRR < -80 and IRSI < IRSI1:
                        print(f"{data['asset']} returning true because of rsi implement")
                        return {'BUY':False,'SELL':True}
                    # elif WRR > -25 and IRSI < IRSI1:
                    #     print(f"{data['asset']} returning true because of wrr implement")
                    #     return {'BUY':True,'SELL':False}

        return {'BUY':False,'SELL':False}
    
    def FiveMinStrategie():
        # momo strategie
        pass

    def TenMinStrategie():
        pass

    def FifteenMinStrategie():
        pass

    def ThirtyMinStrategie():
        pass

    # one of the strategie used for 5 mins chart
    def MomoStrategie():
        # EMA - 20 (Period)
        # MACD - EMA-12, SLOW EMA-26,SIGNAL_LINE-9
        pass



"""
if MCAD in 'BUY' and MOM in 'BUY' and RSI in ('NEUTRAL', 'BUY'):
            if mv['RECOMMENDATION'] in ('BUY', 'STRONG_BUY'):
                if int(IRSI) == int(IRSI1):
                    return {'BUY':False,'SELL':False}
                elif (EMA5 in 'BUY' and SMA5 in 'BUY'):
                    if  IRSI > IRSI1 and mv['RECOMMENDATION'] in ('STRONG_BUY') and WR > -30 and CCI > 100:
                        return {'BUY':False,'SELL':True}
                    elif HullMA in 'BUY' and IRSI < IRSI1:
                        return {'BUY':True,'SELL':False}
                    elif HullMA in 'BUY':
                        return {'BUY':True,'SELL':False}     
        elif MCAD in 'SELL' and MOM in 'SELL' and RSI in ('NEUTRAL', 'SELL'):
            if mv['RECOMMENDATION'] in ('SELL', 'STRONG_SELL'):
                if int(IRSI) == int(IRSI1):
                    return {'BUY':False,'SELL':False}
                elif (EMA5 in 'SELL' and SMA5 in 'SELL'):
                    if  IRSI1 > IRSI and mv['RECOMMENDATION'] in ('STRONG_SELL') and WR < -70 and CCI < -100:
                        return {'BUY':True,'SELL':False}
                    elif HullMA in 'SELL' and IRSI > IRSI1:
                        return {'BUY':False,'SELL':True}
                    elif HullMA in 'SELL':
                        return {'BUY':False,'SELL':True}
        return {'BUY':False,'SELL':False}
"""