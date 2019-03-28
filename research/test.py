import os

import pandas as pd

#from execution import analyze, run
#from strategy import HoldStrategy, KalmanFilterStrategy
from strategy import KalmanFilterStrategy

data_dir = 'data'
exchange = 'test'
sampling_intervals = ['1min', '5min', '15min', '1h', '1d']

df_1m = pd.read_hdf(os.path.join(data_dir, exchange, 'all-1min.h5'))
df_1m.head()

analyze(run(HoldStrategy(), df_1m))
