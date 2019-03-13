import backtrader as bt
import backtrader.analyzers as analyzers
import pandas as pd
import os
from strategies import *


def test_strategy(strategy, data, plot=False):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy)
    data = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(data)
    # Sharpe ratio compares strategy against "risk-free" average S&P 500 APY
    cerebro.addanalyzer(analyzers.SharpeRatio,
                        riskfreerate=0.06, _name='sharpe')
    cerebro.addanalyzer(analyzers.DrawDown, _name='drawdown')

    starting_cash = 10**6
    cerebro.broker.setcash(starting_cash)
    sim = cerebro.run()

    if plot:
        cerebro.plot(style='candlestick')

    return {
        'gain': (cerebro.broker.getvalue() - starting_cash) / starting_cash,
        'sharpe_ratio': sim[0].analyzers.sharpe.get_analysis(),
        'max_drawdown': sim[0].analyzers.drawdown.get_analysis().max.drawdown,
    }


def load_csv(path):
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, unit='ms')
    return df


data_path = 'data/binance'
csvs = ['BTC-USDT-1m-2019-01-01T00-00-00Z-720.csv',
        'BTC-USDT-1m-2010-01-01T00-00-00Z-4836858.csv']
strategies = [SimpleRsiStrategy]

for csv_name in csvs:
    for strategy in strategies:
        print('Evaluating {} on {}...'.format(strategy.__name__, csv_name))
        df = load_csv(os.path.join(data_path, csv_name))
        print(test_strategy(strategy, df))
