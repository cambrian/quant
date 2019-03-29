from abc import ABC, abstractmethod


class Executor(ABC):
    """An abstract class for writing strategy executors.

    Args:
        thread_manager (ThreadManager): A thread manager to attach any child threads for this
            exchange object.

    """

    @abstractmethod
    def __init__(self, thread_manager):
        self._thread_manager = thread_manager

    @abstractmethod
    def _trade_book(self, book):
        """Trades on a particular pair using the latest order book and estimated fair price.

        Args:
            book (OrderBook): An order book for an exchange and pair.

        """
        pass

    @abstractmethod
    def tick_fairs(self, fairs):
        """Retains new price information (for multiple currency pairs).

        Args:
            fairs (Gaussian): A multivariate Gaussian (over a DataFrame) with a variable per
                currency pair.

        """
        pass

    @abstractmethod
    def order_size(self, direction, fees, balance, fair, price):
        """Calculates an order size for a particular pair.

        Args:
            direction (Direction): The desired trade direction.
            fees (dict): Fee structure for an exchange (has `maker` and `taker` fields).
            balance (float): Current balance of base currency.
            fair (float): Estimated fair price for pair.
            price (float): Last trade price for pair.

        Returns:
            float: The order size.

        """
        pass
