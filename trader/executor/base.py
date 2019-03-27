from abc import ABC, abstractmethod


class Executor(ABC):
    """An abstract class for writing strategy executors."""

    @abstractmethod
    def tick(self, fairs):
        """Incorporates new price information to generate and execute orders.

        Args:
            fairs (Gaussian): A multivariate Gaussian (over a DataFrame) with a variable per
                currency.

        """
        pass
