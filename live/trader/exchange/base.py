from trader.util import Feed

from abc import ABC, abstractmethod

_thread_count = 0


class Exchange(ABC):
    """An abstract class for interacting with an exchange."""

    def feed(self, thread_manager, pair, time_interval):
        """Returns a price feed for a particular pair on this exchange.

        Args:
            thread_manager (ThreadManager): A thread manager to run the feed on.
            pair (str): The pair, specified in the format of the exchange.
            time_interval: The time interval for candles, specified in the format of the exchange.

        Returns:
            Feed: A feed of OHLCV candles (see `feed`).

        """
        global _thread_count
        feed = Feed(self._feed(pair, time_interval))
        feed_name = 'exchange-{name}-{pair}-{id}'.format(
            name=self.__class__.__name__.lower(), pair=pair, id=_thread_count)
        thread_manager.attach(feed_name, feed.run)
        _thread_count += 1
        return feed

    @abstractmethod
    def _feed(self, pair, time_interval):
        """Yields OHLCV candles for the given pair and time interval on this exchange.

        Args:
            pair (str): The pair, specified in the format of the exchange.
            time_interval: The time interval for candles, specified in the format of the exchange.

        Yields:
            A dictionary with `timestamp`, `open`, `high`, `low`, `close`, and `volume`, which
                represents a candle for the given pair and time interval.

        """
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
