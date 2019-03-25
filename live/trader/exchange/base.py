from abc import ABC, abstractmethod

import rx
import rx.operators as op

_thread_count = 0


class Exchange(ABC):
    """An abstract class for interacting with an exchange.

    Attributes:
        threads (list): List of feed threads generated for this exchange. Pass this to
            `manage_threads`.
        name (str): A canonical name for this exchange.

    """

    def __init__(self):
        self.threads = []
        self.name = None

    # TODO: Trading/account management functions.
    def observe(self, pair, time_interval):
        """Returns an asychronous price feed for a particular pair on this exchange.

        Args:
            pair (str): The pair, specified in the format of the exchange.
            time_interval: The time interval for candles, specified in the format of the exchange.

        Returns:
            A tuple representing a price feed and containing an Observable.

        """
        global _thread_count
        feed_generator = self._feed(pair, time_interval)
        feed = rx.from_iterable(feed_generator).pipe(op.publish())
        feed_thread = ('exchange-' + self.name.lower() + '-' + pair + '-' + str(_thread_count),
                       feed.connect)
        self.threads.append(feed_thread)
        _thread_count += 1
        return (self.name, pair, feed)

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
