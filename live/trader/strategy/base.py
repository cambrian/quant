from trader.util import MVar

from abc import ABC, abstractmethod
from queue import Queue

import rx
import rx.operators as op

_thread_count = 0


class Strategy(ABC):
    def __init__(self, *data_feeds):
        global _thread_count
        tick_queue = Queue()
        consuming = {}

        # Populate tick queue with data feeds.
        for (exchange, pair, feed) in data_feeds:
            if (exchange, pair) not in consuming:
                consuming[(exchange, pair)] = True
                feed.subscribe_(
                    lambda ohlcv, exchange=exchange, pair=pair:
                        tick_queue.put((exchange, pair, ohlcv)))

        def feed_generator():
            while True:
                exchange, pair, ohlcv = tick_queue.get()
                yield self._tick(exchange, pair, ohlcv)

        self.feed = rx.from_iterable(feed_generator()).pipe(op.publish())
        self.thread = ('strategy-' + self.__class__.__name__.lower() + '-' + str(_thread_count),
                       self.feed.connect)
        _thread_count += 1

    @abstractmethod
    def _tick(self, exchange, pair, ohlcv):
        # Returns a list of (exchange, pair, fair_price, std_dev, [auxiliary_data]).
        pass
