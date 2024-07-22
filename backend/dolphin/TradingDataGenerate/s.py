from main import TvDatafeed, Interval


s = TvDatafeed('mageshragav1@gmail.com','Magesh1@')
# for i in ['EURAUD','EURUSD','EURCAD','EURJPY','EURGBP','USDCAD','USDJPY']:
#     m = s.get_hist(symbol=f'{i}',exchange='FX',interval=Interval.in_5_minute,n_bars=9999,extended_session=True)
# #     # m.to_csv('common/MachineLearningModel/output/one_mins/EURCAD_1_Min.csv')
# #     # m.to_csv('common/MachineLearningModel/output/one_mins/EURJPY_1_Min.csv')
# #     # m.to_csv('common/MachineLearningModel/output/one_mins/EURUSD_1_Min.csv')
#     m.to_csv(f'common/MachineLearningModel/output/five_mins/{i}_5_Min_4.csv')

m = s.get_hist(symbol=f'EURUSD',exchange='FX',interval=Interval.in_5_minute,n_bars=9999,extended_session=False)
m.to_csv(f'common/MachineLearningModel/output/five_mins/EURUSD_5_Min_testing_new.csv')