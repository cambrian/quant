from trader.strategy.base import Strategy
from trader.util.constants import BITFINEX, KRAKEN
from trader.util.stats import MovingAverage

from numpy_ringbuffer import RingBuffer

import numpy as np


class Dummy(Strategy):
    """A shitty strategy for testing purposes."""

    def __init__(self, thread_manager, price_feeds):
        super().__init__(thread_manager, price_feeds)
        self.ma = MovingAverage(30)
        self.prices = RingBuffer(capacity=15, dtype=float)

    def expected_price_feeds(self):
        return {
            (BITFINEX, 'BTCUSD', '1m')
        }

    def _tick(self, exchange, pair, time_interval, ohlcv):
        print(exchange, pair, time_interval, ohlcv)
        if exchange == BITFINEX and pair == 'BTCUSD' and time_interval == '1m':
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
