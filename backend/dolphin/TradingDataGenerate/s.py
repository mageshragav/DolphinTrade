from main import TvDatafeed, Interval


s = TvDatafeed()
m = s.get_hist(symbol='EURJPY',exchange='FX',interval=Interval.in_5_minute,n_bars=10000,extended_session=True)
m.to_csv('EURJPY_5_Min.csv')

