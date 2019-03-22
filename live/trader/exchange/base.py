from abc import ABC, abstractmethod

import rx
import rx.operators as op

_thread_count = 0


class Exchange(ABC):
    def __init__(self):
        self.threads = []
        self.name = None

    # TODO: Trading/account management functions.
    def observe(self, pair, time_interval):
        global _thread_count
        feed_generator = self._feed(pair, time_interval)
        feed = rx.from_iterable(feed_generator).pipe(op.publish())
        feed_thread = ('exchange-' + self.__class__.__name__.lower() + '-' + pair + '-'
                       + str(_thread_count), feed.connect)
        self.threads.append(feed_thread)
        _thread_count += 1
        return (self.name, pair, feed)

    @abstractmethod
    def _feed(self, pairs, time_interval):
        # Repeatedly `yield` new data at each tick.
        pass

    @abstractmethod
    def add_order(self, pair, side, order_type, price, volume):
        # Param side is buy/sell.
        # Param order_type is limit/market/other exchange specific options.
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        pass

    @abstractmethod
    def get_balance(self):
        pass

    @abstractmethod
    def get_open_positions(self):
        pass
