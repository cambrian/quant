from abc import ABC, abstractmethod


class Strategy(ABC):
    """An abstract class for writing strategies."""

    # TODO: possibly do more during initialization, such as passing in the set of pairs/exchanges

    @abstractmethod
    def tick(self, frame):
        """The actual implementation of a strategy.

        Strategies should take the feed data received at each tick and incorporate it into their
        running models of the market.

        Args:
            frame: Pandas dataframe with the following structure
                    price   volume
            AAA_XXX 1       100
            BBB_XXX 2       200
            ...
            ZZZ_XXX p       v

        Returns:
            Gaussian: A multivariate Gaussian (over a DataFrame) with a variable per currency pair.

        """
        pass
