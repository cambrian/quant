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
            DataFrame: A Pandas dataframe of book entries (side/price/volume).

        """
        pass

    @abstractmethod
    def prices(self, pairs, time_frame):
        """Queries prices and volumes for the given pairs.

        Args:
            pairs (str): A list of pairs to query.
            time_frame (type depends on exchange): granularity of pricing data, in
            exchange's format.

        Returns:
            DataFrame: A Pandas dataframe of prices and volumes indexed by the pairs.

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
