from abc import ABC, abstractmethod
from math import sqrt
import pandas as pd
import numpy as np


class Strategy(ABC):
    @abstractmethod
    def step(self, prices, volumes):
        '''Should return fairs as multi-variate Gaussian.'''
        pass

    def null_estimate(self, prices):
        '''Returns fair estimates centered at the given prices with very low confidence.'''
        mean = prices
        variance = prices.replace(prices, 1e100)
        return Gaussian(mean, variance)


class CombinedStrategy(Strategy):
    def __init__(self, strategies):
        self.strategies = strategies

    def step(self, prices, volumes):
        fairs = [s.step(prices, volumes) for s in self.strategies]
        # TODO: populate fairs with 0-mean, high variance values for any pairs not shared
        return Gaussian.join(fairs)


class HoldStrategy(Strategy):
    '''Always returns null estimate.'''

    def step(self, prices, _volumes):
        return self.null_estimate(prices)


class MovingAverage:
    def __init__(self, half_life):
        self.__a = 0.5 ** (1 / half_life)
        self.__value = None
        self.__samples_needed = half_life

    @property
    def value(self):
        return self.__value

    def step(self, value):
        if self.__value is None:
            self.__value = value
        self.__value = self.__a * self.__value + (1-self.__a) * value
        self.__samples_needed = max(0, self.__samples_needed - 1)

    @property
    def ready(self):
        return self.__samples_needed == 0


class Gaussian:
    '''Single or multi-variate gaussian. For multi-variate gaussians, simply set mean and variance
    to numpy vectors or pandas series. Does not check that the dimension of mean and variance match.
    TODO: consider marshalling everything into numpy or pandas
    '''

    def __init__(self, mean, variance):
        self.mean = mean
        self.variance = variance

    @property
    def stddev(self):
        if (isinstance(self.variance, pd.Series)):
            return self.variance.apply(sqrt)
        return np.sqrt(self.variance)

    def __add__(self, scalar):
        '''Add a scalar to the gaussian. For the sum of i.i.d gaussians see `sum`.'''
        return Gaussian(self.mean + scalar, self.variance)

    @staticmethod
    def sum(xs):
        '''Sum of many I.I.D. gaussian variables.
        TODO: this probably doesn't work for numpy/pandas representations
        '''
        return Gaussian(sum([x.mean for x in xs]), sum([x.variance for x in xs]))

    @staticmethod
    def join(xs):
        '''
        Joint-probability distribution of many gaussians. Input gaussians must be in the same space.
        Currently implemented for mean, variance of type pd.Series. Equivalent to chaining `&`s but
        is probably faster.
        TODO: implement for plain types?
        TODO: check that input observations make sense

        >>> Gaussian.join([Gaussian(3,5), Gaussian(4,15), Gaussian(5,25)])
        mean:
        0    3.478261
        dtype: float64
        variance:
        0    3.26087
        dtype: float64
        <BLANKLINE>

        >>> Gaussian.join([])
        mean:
        Series([], dtype: float64)
        variance:
        Series([], dtype: float64)
        <BLANKLINE>

        >>> Gaussian.join([Gaussian(1,1)])
        mean:
        0    1.0
        dtype: float64
        variance:
        0    1.0
        dtype: float64
        <BLANKLINE>
        '''

        means = pd.DataFrame([x.mean for x in xs])
        variances = pd.DataFrame([x.variance for x in xs])
        variance_partial_product = (variances.product() / variances)
        mean = (variance_partial_product * means).sum() / variance_partial_product.sum()
        variance = variances.product() / variance_partial_product.sum()

        return Gaussian(mean, variance)

    def __and__(self, x):
        '''
        Joint-probability distribution of two gaussians.
        For joint-probability of >2 gaussians see `join`.
        >>> Gaussian(5,5) & Gaussian(5,5)
        mean:
        5.0
        variance:
        2.5
        <BLANKLINE>
        >>> Gaussian(3,5) & Gaussian(4,15) & Gaussian(5,25)
        mean:
        3.4782608695652173
        variance:
        3.260869565217391
        <BLANKLINE>
        '''
        mean = (self.mean * x.variance + x.mean * self.variance) / (self.variance + x.variance)
        variance = self.variance * x.variance / (self.variance + x.variance)
        return Gaussian(mean, variance)

    def __mul__(self, scalar):
        '''Scalar multiplication. For the product of two PDFs see __and__, and for the product of
        two i.i.d. variables see __matmul__.'''
        return Gaussian(self.mean * scalar, self.variance * scalar * scalar)

    def __matmul__(self, x):
        '''Multiplication of two i.i.d. gaussian variables. The result is NOT gaussian but we return
        a gaussian approximation with the same mean and variance.'''
        mean = self.mean * x.mean
        variance = (self.variance + x.mean * x.mean) * (x.variance + self.mean * self.mean) - \
            (self.mean * self.mean * x.mean * x.mean)
        return Gaussian(mean, variance)

    def __sub__(self, x):
        return self + -x

    def __div__(self, scalar):
        return self * (1/scalar)

    def __repr__(self):
        return 'mean:\n' + repr(self.mean) + '\nvariance:\n' + repr(self.variance) + '\n'
