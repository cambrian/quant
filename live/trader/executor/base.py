from abc import ABC, abstractmethod


class Executor(ABC):
    """An abstract class for writing strategy executors."""

    @abstractmethod
    def tick(self, fairs):
        """Incorporates new price information to generate and execute orders.

        Args:
            fairs (dict): A dictionary of Gaussian fairs by ticker symbol.

        """
        pass
