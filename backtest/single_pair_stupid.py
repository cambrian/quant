#!/usr/bin/env python
# pip3 install ccxt
# pip3 install pandas
# pip3 install backtrader
# pip3 install matplotlib

import populator
import backtrader as bt


class RsiStrategy(bt.Strategy):
    def __init__(self):
        self.rsi = bt.indicators.RSI_SMA(
            self.data.close, period=21, safediv=True)

    def next(self):
        if not self.position:
            if self.rsi < 30:
                self.buy(size=10)
        else:
            if self.rsi > 70:
                self.sell(size=10)


class MaCrossOverStrategy(bt.Strategy):
    params = (
        ('fast', 10),
        ('slow', 30),
        ('_movav', bt.indicators.MovAv.SMA)
    )

    def __init__(self):
        sma_fast = self.p._movav(period=self.p.fast)
        sma_slow = self.p._movav(period=self.p.slow)
        self.buysig = bt.indicators.CrossOver(sma_fast, sma_slow)

    def next(self):
        if self.position.size:
            if self.buysig < 0:
                self.sell(size=10)

        elif self.buysig > 0:
            self.buy(size=10)


btc_usdt = populator.load_data_as_frame(
    'data', 'binance', 'BTC/USDT', '1m', '2000-01-01T00:00:00Z')
eth_usdt = populator.load_data_as_frame(
    'data', 'binance', 'ETH/USDT', '1m', '2000-01-01T00:00:00Z')
xrp_usdt = populator.load_data_as_frame(
    'data', 'binance', 'XRP/USDT', '1m', '2000-01-01T00:00:00Z')
ltc_usdt = populator.load_data_as_frame(
    'data', 'binance', 'LTC/USDT', '1m', '2000-01-01T00:00:00Z')
eos_usdt = populator.load_data_as_frame(
    'data', 'binance', 'EOS/USDT', '1m', '2000-01-01T00:00:00Z')


def run_test(strategy, name, data, plot=False):
    print('Running {} on {}.'.format(strategy.__name__, name))

    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy)
    data = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(data)
    # Sharpe ratio compares strategy against "risk-free" average S&P 500 APY.
    cerebro.addanalyzer(bt.analyzers.SharpeRatio,
                        riskfreerate=0.06, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

    starting_cash = 10**5
    cerebro.broker.setcash(starting_cash)
    sim = cerebro.run()

    if plot:
        cerebro.plot(style='candlestick')

    print('PNL %: {}'.format(
        (cerebro.broker.getvalue() - starting_cash) / starting_cash - 1.0))
    print('Sharpe Ratio: {}'.format(
        sim[0].analyzers.sharpe.get_analysis()['sharperatio']))
    print('Max Drawdown: {}'.format(
        sim[0].analyzers.drawdown.get_analysis().max.drawdown))


strategies = [RsiStrategy, MaCrossOverStrategy]
pairs = [
    ('BTC/USDT', btc_usdt),
    ('ETH/USDT', eth_usdt),
    ('XRP/USDT', xrp_usdt),
    ('LTC/USDT', ltc_usdt),
    ('EOS/USDT', eos_usdt)
]

for strategy in strategies:
    for (name, data) in pairs:
        run_test(strategy, name, data)
