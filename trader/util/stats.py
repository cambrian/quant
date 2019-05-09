"""The `statistics` module.

Helpful statistical models and indicators.

Note: In literature on moving averages, you'll see "value" referred to as "level".

"""

import numpy as np
import pandas as pd
from pandas.core.indexes.range import RangeIndex
from scipy.spatial.distance import mahalanobis
from scipy.special import binom as choose
from scipy.stats import multivariate_normal


class Ema:
    """
    Exponentially-weighted moving average.
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

    def step(self, x):
        if self.__value is None:
            self.__value = x
        self.__value = self.__a * self.__value + (1 - self.__a) * x
        self.__samples_needed = max(0, self.__samples_needed - 1)
        return self.__value

    @property
    def ready(self):
        return self.__samples_needed == 0


class DoubleEma:
    """
    Note: In general, prefer HoltEma.

    Double ema. Like the simple ema, but also extrapolates based on trend to compensate for lag.
    Equivalent to 2 * Ema(x) - Ema(Ema(x)).
    """

    def __init__(self, half_life):
        self.__e = Ema(half_life)
        self.__ee = Ema(half_life)

    @property
    def value(self):
        return 2 * self.__e.value - self.__ee.value

    def step(self, x):
        self.__e.step(x)
        self.__ee.step(self.__e.value)
        return self.value

    @property
    def ready(self):
        return self.__e.ready


class HoltEma:
    """
    Holt's linear exponential smoothing. In addition to estimating a moving value, also estimates
    trend and incorporates that into value updates. Extrapolation can be performed using the trend.

    Implementation from https://people.duke.edu/~rnau/411avg.htm
    """

    def __init__(self, value_half_life, trend_half_life):
        self.__a = 0.5 ** (1 / value_half_life)
        self.__b = 0.5 ** (1 / trend_half_life)
        self.__value = None
        self.__trend = None
        self.__samples_needed = max(value_half_life, trend_half_life)

    @property
    def value(self):
        return self.__value

    @property
    def trend(self):
        return self.__trend

    def step(self, x):
        if self.__value is None:
            self.__value = x
            self.__trend = 0
        value_old = self.__value
        self.__value = (1 - self.__a) * x + self.__a * (self.__value + self.__trend)
        self.__trend = (1 - self.__b) * (self.__value - value_old) + self.__b * self.__trend
        self.__samples_needed = max(0, self.__samples_needed - 1)
        return self.__value

    @property
    def ready(self):
        return self.__samples_needed == 0
