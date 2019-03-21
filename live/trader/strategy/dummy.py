from trader.strategy.base import Strategy


class Dummy(Strategy):
    def _tick(self, exchange, pair, ohlcv):
        # TODO: Strategy to derive fair estimate and stddev.
        print(ohlcv)
        print(ohlcv[1][5])
        fair = float(ohlcv[1][5])
        stddev = 100.0
        return ((fair, stddev), ohlcv)
