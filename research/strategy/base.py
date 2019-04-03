from abc import ABC, abstractmethod
from math import sqrt

from trader.util.stats import Gaussian


class Strategy(ABC):
    @abstractmethod
    def step(self, frame):
        """Should return fairs as multi-variate Gaussian."""
        pass

    def null_estimate(self, prices):
        """Returns fair estimates centered at the given prices with very low confidence."""
        mean = prices
        variance = prices.replace(prices, 1e100)
        return Gaussian(mean, variance)


class CombinedStrategy(Strategy):
    def __init__(self, strategies):
        self.strategies = strategies

    def step(self, frame):
        fairs = [s.step(frame) for s in self.strategies]
        # TODO: populate fairs with 0-mean, high variance values for any pairs not shared
        return Gaussian.intersect(fairs)


class HoldStrategy(Strategy):
    """Always returns null estimate."""

    def step(self, frame):
        return self.null_estimate(frame["price"])
