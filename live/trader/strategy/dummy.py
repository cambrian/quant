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
        if exchange == KRAKEN and pair == 'XBT/USD':
            close = float(ohlcv['close'])
            self.prices.append(close)
            stddev = np.std(np.array(self.prices))
            self.ma.step(close)
            return [(exchange, pair, self.ma.value, stddev, ohlcv)]
        return []
