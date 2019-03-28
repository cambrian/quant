from abc import ABC, abstractmethod

from trader.util import Feed


class Exchange(ABC):
    """An abstract class for interacting with an exchange."""

    def book(self, pair):
        """Returns a stream of order books for the given pair.

        Args:
            pair (str): The pair to stream.

        Returns:
            Feed: A feed of book dataframes (see `_book`).

        """
        return Feed(self._book(pair))

    @abstractmethod
    def _book(self, pair):
        """Generates a stream of order books for the given pair.

        Args:
            pair (str): The pair to stream.

        Yields:
            tuple: Order book tuple of (exchange, pair, best bid, best ask). TODO: This can be
                easily made to return more levels in the book (when we want that).

        """
        pass

    def track_balances(self, pair):
        """Returns a function to dynamically track and update internal balance state.

        Args:
            pair (str): The pair to track.

        """
        pass

    @abstractmethod
    def prices(self, pairs, time_frame):
        """Queries prices and volumes for the given pairs.

        Args:
            pairs (str): A list of pairs to query.
            time_frame (type depends on exchange): Granularity of pricing data, in the exchange's
                format.

        Returns:
            DataFrame: A Pandas dataframe of prices and volumes indexed by the pairs.

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

    @property
    @abstractmethod
    def balances(self):
        """Queries exchange object for tracked balances.

        Returns:
            dict: Map of currency to held volume.

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
    def get_open_positions(self):
        pass
