import os
import time

import pandas as pd
from hyperopt import STATUS_OK, Trials, fmin, hp, tpe

from research.execution import analyze, run
from research.strategy import KalmanFilterStrategy

data_dir = 'research/data'
exchange = 'test'
sample_intervals = ['1min', '5min', '15min', '1h', '1d']
start_date = '2019-03-13 00:00:00'

dfs = {}
for interval in sample_intervals:
    df = pd.read_hdf(os.path.join(data_dir, exchange, 'all-{}.h5'.format(interval)))
    dfs[interval] = df.loc[start_date:]


def objective(arg_dict):
    strat = KalmanFilterStrategy(
        correlation_window_size=arg_dict['cws'],
        movement_half_life=arg_dict['mhl']
    )
    rommr = analyze(run(strat, dfs['1min'], fractional_fee=0.001), plot=False)
    return {'loss': -rommr, 'status': STATUS_OK, 'time': time.time()}


search_space = {
    'cws': hp.choice('cws', list(range(1, 1001))),
    'mhl': hp.choice('mhl', list(range(1, 201))),
}

trials = Trials()
best_cws = fmin(objective, space=search_space, algo=tpe.suggest, max_evals=1000, trials=trials)

pd.DataFrame(trials.trials).to_csv('kalman_1m_opt.csv')
