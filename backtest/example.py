import backtrader as bt
import backtrader.analyzers as analyzers
import pandas as pd
import populator
import os


class SimpleRsiStrategy(bt.Strategy):
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


def test_strategy(strategy, data, plot=False):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(strategy)
    data = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(data)
    # Sharpe ratio compares strategy against "risk-free" average S&P 500 APY.
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


print('Evaluating SimpleRsiStrategy on Binance BTC/USDT.')
df = populator.load_data_as_frame(
    'data', 'binance', 'BTC/USDT', '1m', '2000-01-01T00:00:00Z')
print(test_strategy(SimpleRsiStrategy, df))
