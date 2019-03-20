from abc import ABC, abstractmethod

import rx


class Exchange(ABC):
    # TODO: Trading/account management functions.
    def observe(self, pairs, time_interval):
        feed_generator = self._feed(pairs, time_interval)
        return rx.from_iterable(feed_generator)

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
