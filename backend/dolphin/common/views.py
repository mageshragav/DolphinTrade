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
        # 'COMPUTE': {'EMA10': 'SELL', 'SMA10': 'SELL', 'EMA20': 'SELL',
        # 'SMA20': 'SELL', 'EMA30': 'BUY', 'SMA30': 'BUY', 'EMA50': 'BUY',
        # 'SMA50': 'BUY', 'EMA100': 'BUY', 'SMA100': 'BUY', 'EMA200': 'BUY',
        # 'SMA200': 'BUY', 'Ichimoku': 'NEUTRAL', 'VWMA': 'SELL', 'HullMA': 'BUY'}}
        return mv
    
    def personal_recommendation(self,data, oscillator):
        RSI = oscillator['COMPUTE']['RSI']
        MCAD = oscillator['COMPUTE']['MACD']
        personal_recommond = ''
        if not (RSI == 'NEUTRAL' or MCAD == 'NEUTRAL'):
            personal_recommond = 'SELL' if RSI in ('SELL','STRONG_SELL') and MCAD in ('SELL','STRONG_SELL') else 'BUY'
        if data['RECOMMENDATION'] == 'STRONG_BUY':
            return {'BUY':True,'SELL':False}
        elif data['RECOMMENDATION'] == 'STRONG_SELL':
            return {'BUY':False,'SELL':True}
        else:
            # if data['BUY'] > data['SELL']:
            #     if data['BUY'] - data['SELL'] > 4 and data['NEUTRAL'] < 10:
            #         return {'BUY':True,'SELL':False}
            # else:
            #     if data['SELL'] - data['BUY'] > 4 and data['NEUTRAL'] < 10:
            #         return {'BUY':False,'SELL':True}
            if data['NEUTRAL'] < 10:
                if data['BUY'] > 12 and data['SELL'] < 5:
                    if personal_recommond == 'BUY':
                        return {'BUY':True,'SELL':False}
                elif data['SELL'] > 12 and data['BUY'] < 5:
                    if personal_recommond == 'SELL':
                        return {'BUY':False,'SELL':True}
        return {'BUY':False,'SELL':False}