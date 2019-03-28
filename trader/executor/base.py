from abc import ABC, abstractmethod


class Executor(ABC):
    """An abstract class for writing strategy executors."""

    @abstractmethod
    def tick_book(self, book):
        """Reacts to order book information (for different exchanges and pairs) by placing orders in
        the market.

        Args:
            book (tuple): An order book info tuple (exchange, pair, (latest bid, latest ask)).

        """
        pass

    @abstractmethod
    def tick_fairs(self, fairs):
        """Incorporates new price information into the executor's world model.

        Args:
            fairs (Gaussian): A multivariate Gaussian (over a DataFrame) with a variable per
                currency.

        """
        pass

    @abstractmethod
    def order_size(self, direction, fees, balance, fair, price):
        """TODO: Finalize signature for this."""
        pass
