from abc import ABC, abstractmethod
from aiostream import stream


class Exchange(ABC):
    # TODO: Trading/account management functions.
    def observe(self, pairs, time_interval):
        feed_generator = self._feed(pairs, time_interval)
        return stream.iterate(feed_generator)

    @abstractmethod
    async def _feed(self, pairs, time_interval):
        # Repeatedly `yield` new data at each tick.
        pass

    @abstractmethod
    async def add_order(self, pair, side, order_type, price, volume):
        # Param side is buy/sell.
        # Param order_type is limit/market/other exchange specific options.
        pass

    @abstractmethod
    async def cancel_order(self, order_id):
        pass

    @abstractmethod
    async def get_balance(self):
        pass

    @abstractmethod
    async def get_open_positions(self):
        pass
