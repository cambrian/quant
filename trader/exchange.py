from abc import ABC, abstractmethod
from aiostream import stream


class Exchange(ABC):
    # TODO: Trading/account management functions.
    def observe(self, pairs, time_interval):
        feed_generator = self._feed(pairs, time_interval)
        return stream.iterate(feed_generator)

    @abstractmethod
    def _feed(self, pairs, time_interval):
        # Repeatedly `yield` new data at each tick.
        pass

    @abstractmethod
    def add_order(self, pair, side, ordertype, price, volume):
        # side is buy/sell, ordertype is limit/market/other ex specific options
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
