import backtrader as bt


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
