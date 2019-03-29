from abc import ABC, abstractmethod


class Strategy(ABC):
    """An abstract class for writing strategies."""

    @abstractmethod
    def tick(self, *args):
        """The actual implementation of a strategy.

        Strategies should take the feed data received at each tick and incorporate it into their
        running models of the market.

        Args:
            *args: Any arguments to your strategy. These will typically be Pandas dataframes with
                price data for each exchange you care about.

        Returns:
            Gaussian: A multivariate Gaussian (over a DataFrame) with a variable per currency pair.

        """
        pass
