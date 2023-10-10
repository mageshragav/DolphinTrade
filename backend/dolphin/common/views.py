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
        MCAD = oscillator['COMPUTE']['MACD']
        MOM = oscillator['COMPUTE']['Mom']
        BBP = oscillator['COMPUTE']['BBP']
        CCI = oscillator['COMPUTE']['CCI']
        WR = oscillator['COMPUTE']['W%R']
        STOCHK = oscillator['COMPUTE']['STOCH.K']
        STOCHRSI = oscillator['COMPUTE']['Stoch.RSI']
        EMA5 = 'SELL' if indicator['EMA5'] > indicator['close'] else 'BUY'
        SMA5 = 'SELL' if indicator['SMA5'] > indicator['close'] else 'BUY'
        os_data = {'RSI': RSI,'MACD':MCAD,'MOM':MOM,'BBP':BBP,'CCI':CCI,'WR':WR}
        buy_value = [True if i == 'BUY' else False for i in {'MACD':MCAD,'MOM':MOM}.values()]
        sell_value = [True if i == 'SELL' else False for i in {'MACD':MCAD,'MOM':MOM}.values()]
        os_sell_count = [True if i == 'SELL' else False for i in os_data.values()]
        os_buy_count = [True if i == 'BUY' else False for i in os_data.values()]
        if any([True if i == 'BUY' else False for i in [STOCHK,STOCHRSI]]) and WR == 'BUY' and CCI == 'BUY':
            return {'BUY':True,'SELL':False}
        elif any([True if i == 'SELL' else False for i in [STOCHK,STOCHRSI]]) and WR == 'SELL' and CCI == 'SELL':
            return {'BUY':False,'SELL':True}
        elif all(buy_value):
            if EMA5 == 'BUY' and SMA5 == 'BUY' and MCAD == 'BUY':
                return {'BUY':True,'SELL':False}
            elif os_buy_count.count(True) >= 2:
                return {'BUY':True,'SELL':False}
        elif all(sell_value):
            if EMA5 == 'SELL' and SMA5 == 'SELL' and MCAD == 'SELL':
                return {'BUY':False,'SELL':True}
            elif os_sell_count.count(True) >= 2:
                return {'BUY':False,'SELL':True}
        return {'BUY':False,'SELL':False}
        # personal_recommond = 'NEUTRAL'
        # if data['RECOMMENDATION'] in ('STRONG_BUY', 'BUY'):
        #     # if (EMA5 in 'BUY' or SMA5 in 'BUY') and MOM in 'BUY':
        #     return {'BUY':True,'SELL':False}
        # elif data['RECOMMENDATION'] in ('STRONG_SELL', 'SELL'):
        #     # if (EMA5 in 'SELL' or SMA5 in 'SELL') and MOM in 'SELL':
        #     return {'BUY':False,'SELL':True}
        # return {'BUY':False,'SELL':False}
    
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
