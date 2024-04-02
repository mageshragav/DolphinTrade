from main import TvDatafeed, Interval


s = TvDatafeed('mageshragav1@gmail.com','Magesh1@')
m = s.get_hist(symbol='EURCAD',exchange='FX',interval=Interval.in_15_minute,n_bars=9999,extended_session=True)
m.to_csv('common/MachineLearningModel/output/fifteen_mins/EURCAD_15_Min.csv')

