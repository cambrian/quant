from abc import ABC, abstractmethod
from enum import Enum

from trader.util import Feed


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
        pass

    @abstractmethod
    def book_feed(self, pair):
        """Runs and returns a `Feed` of order books for the given pair. If this function is called
        twice with the same pair, it should behave in an idempotent manner.

        Args:
            pair (Constant): The pair to stream.

        Returns:
            Feed: A feed of `OrderBook`.

        """
        pass

    @abstractmethod
    def prices(self, pairs, time_frame):
        """Queries prices and volumes for the given pairs. Reads the latest tracked prices from the
        exchange object.

        Args:
            pairs (list): A list of pairs to query.
            time_frame (type depends on exchange): Granularity of volume data, in the exchange's
                format. If None is passed, volume is not included.

        Returns:
            DataFrame: A Pandas dataframe of prices and volumes indexed by the pairs.

        """
        pass

    @abstractmethod
    def balances_feed(self):
        """Runs and returns a `Feed` of balances for the exchange account. This function should
        behave in an idempotent manner.

        Returns:
            Feed: A feed of maps from currency to held size.

        """
        pass

    @property
    @abstractmethod
    def balances(self):
        """Reads the latest tracked balances from the exchange object.

        Returns:
            dict: Map of currency to held size.

        """
        pass

    @property
    @abstractmethod
    def fees(self):
        """Queries exchange fees for the given pairs.

        Returns:
            dict: Map of maker/taker to fee set by exchange.

        """
        pass

    @abstractmethod
    def add_order(self, pair, side, order_type, price, volume):
        # Param side is buy/sell.
        # Param order_type is limit/market/other exchange specific options.
        # TODO: Unify formats across exchanges.
        pass

    @abstractmethod
    def cancel_order(self, order_id):
        pass

    @abstractmethod
    def get_open_positions(self):
        pass
