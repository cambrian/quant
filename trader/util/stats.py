"""The `statistics` module.

Helpful statistical models and indicators.

"""

import numpy as np
import pandas as pd
from pandas.core.indexes.range import RangeIndex
from scipy.spatial.distance import mahalanobis
from scipy.special import binom as choose
from scipy.stats import multivariate_normal


class Ema:
    """
    An exponential moving average.

    Args:
        half_life (float): The half life (in steps) for the weights of new samples.
    """

    def __init__(self, half_life):
        self.__a = 0.5 ** (1 / half_life)
        self.__value = None
        self.__samples_needed = half_life

    @property
    def a(self):
        return self.__a

    @property
    def value(self):
        return self.__value

    def step(self, value):
        if self.__value is None:
            self.__value = value
        self.__value = self.__a * self.__value + (1 - self.__a) * value
        self.__samples_needed = max(0, self.__samples_needed - 1)

    @property
    def ready(self):
        return self.__samples_needed == 0


class DoubleEma:
    """
    Double ema. Like the simple ema, but also extrapolates based on trend to compensate for lag.
    Equivalent to 2 * Ema(x) - Ema(Ema(x)).

    Args:
        half_life (float): The half life (in steps) for the weights of new samples.
    """

    def __init__(self, half_life):
        self.__e = Ema(half_life)
        self.__ee = Ema(half_life)

    @property
    def value(self):
        return 2 * self.__e.value - self.__ee.value

    def step(self, value):
        self.__e.step(value)
        self.__ee.step(self.__e.value)

    @property
    def ready(self):
        return self.__e.ready
