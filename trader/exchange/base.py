from abc import ABC, abstractmethod


class ExchangeError(Exception):
    pass


class Exchange(ABC):
    """An abstract class for interacting with an exchange.

    Args:
        thread_manager (ThreadManager): A thread manager to attach any child threads for this
            exchange object.

    """

    @abstractmethod
    def __init__(self, thread_manager):
        self._thread_manager = thread_manager

    @property
    @abstractmethod
    def id(self):
        """A canonical name for this exchange.

        Returns:
            string: Exchange id.

        """

    @staticmethod
    @abstractmethod
    def encode_trading_pair(pair):
        """Encode a TradingPair to a string recognizable by the exchange"""

    @staticmethod
    @abstractmethod
    def decode_trading_pair(pair_string):
        """Parse a Tradingpair from a string given by the exchange"""

    @abstractmethod
    def book_feed(self, pair):
        """Runs and returns a `Feed` of order books for the given pair. If this function is called
        twice with the same pair, it should behave in an idempotent manner.

        Args:
            pair (Constant): The pair to stream.

        Returns:
            Feed: A feed of `OrderBook`.

        """

    @abstractmethod
    def frame(self, pairs):
        """Get latest trade prices and cumulative volumes since the previous call to `frame` for
        the given pairs.

        Returns:
            DataFrame: A Pandas dataframe of prices and volumes indexed by the pairs.

        """

    @abstractmethod
    def positions_feed(self):
        """Runs and returns a `Feed` of positions for the exchange account. This function should
        behave in an idempotent manner.

        Returns:
            Feed: A feed of maps from currency to held size.

        """

    @property
    @abstractmethod
    def positions(self):
        """Reads the latest tracked positions from the exchange object.

        Returns:
            dict: Map of currency to held size.

        """

    @property
    @abstractmethod
    def fees(self):
        """Queries exchange fees for the given pairs.

        Returns:
            dict: Map of maker/taker to fee set by exchange.

        """

    @abstractmethod
    def add_order(self, order):
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        pass

    @abstractmethod
    def get_open_positions(self):
        pass

    @abstractmethod
    def get_warmup_data(self, pairs, duration, resolution):
        pass
