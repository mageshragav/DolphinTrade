from main import TvDatafeed, Interval


s = TvDatafeed('mageshragav1@gmail.com','Magesh1@')
m = s.get_hist(symbol='GBPUSD',exchange='FX',interval=Interval.in_15_minute,n_bars=9999,extended_session=True)
# m.to_csv('common/MachineLearningModel/output/one_mins/EURCAD_1_Min.csv')
# m.to_csv('common/MachineLearningModel/output/one_mins/EURJPY_1_Min.csv')
# m.to_csv('common/MachineLearningModel/output/one_mins/EURUSD_1_Min.csv')
m.to_csv('common/MachineLearningModel/output/fifteen_mins/GBPUSD_15_Min_1.csv')

