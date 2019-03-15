#!/usr/bin/env python
# pip3 install ccxt
# pip3 install pandas
# pip3 install backtrader
# pip3 install matplotlib

import populator
import backtrader as bt
import pandas as pd


class PairStrategy(bt.Strategy):
    def __init__(self):
        # TODO
        pass

    def next(self):
        # TODO
        pass


btc_usdt = populator.resample_to('D', populator.load_data_as_frame(
    'data', 'binance', 'BTC/USDT', '1m', '2000-01-01T00:00:00Z'))
ltc_usdt = populator.resample_to('D', populator.load_data_as_frame(
    'data', 'binance', 'LTC/USDT', '1m', '2000-01-01T00:00:00Z'))


cerebro = bt.Cerebro()
cerebro.addstrategy(PairStrategy)
data_0 = bt.feeds.PandasData(dataname=btc_usdt)
data_1 = bt.feeds.PandasData(dataname=ltc_usdt)
cerebro.adddata(data_0)
cerebro.adddata(data_1)

cerebro.addanalyzer(bt.analyzers.SharpeRatio,
                    riskfreerate=0.00, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

starting_cash = 10**5
cerebro.broker.setcash(starting_cash)
sim = cerebro.run()

print('PNL %: {}'.format(
    100.0 * (cerebro.broker.getvalue() / starting_cash) - 100.0))
print('Sharpe Ratio: {}'.format(
    sim[0].analyzers.sharpe.get_analysis()['sharperatio']))
print('Max Drawdown: {}'.format(
    sim[0].analyzers.drawdown.get_analysis().max.drawdown))
