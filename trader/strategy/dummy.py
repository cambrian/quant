from trader.strategy.base import Strategy
from trader.util.stats import Gaussian


class Dummy(Strategy):
    """A shitty strategy for testing purposes."""

    def tick(self, prices):
        # TODO
        return Gaussian([1], [1])
