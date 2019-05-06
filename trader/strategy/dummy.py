import pandas as pd

from trader.strategy.base import Strategy
from trader.util import Gaussian


class Dummy(Strategy):
    """A strategy that always returns a null prediction."""

    def tick(self, frame):
        return Gaussian(pd.Series([]), [])
