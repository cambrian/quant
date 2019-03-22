from trader.constants import BITFINEX, KRAKEN
from trader.strategy.base import Strategy
from trader.util import MovingAverage

from numpy_ringbuffer import RingBuffer

import numpy as np


class Dummy(Strategy):
    def __init__(self, *data_feeds):
        super().__init__(*data_feeds)
        self.ma = MovingAverage(30)
        self.prices = RingBuffer(capacity=15, dtype=float)

    def _tick(self, exchange, pair, ohlcv):
        print(exchange, pair, ohlcv)
        if exchange == BITFINEX and pair == 'BTCUSD':
            close = float(ohlcv['close'])
            self.prices.append(close)
            if len(self.prices) == self.prices.maxlen:
                std_dev = np.std(np.array(self.prices))
                self.ma.step(close)
                return [(exchange, pair, {
                    'fair_price': self.ma.value,
                    'std_dev': std_dev,
                    'ohlcv': ohlcv
                })]
        return []
