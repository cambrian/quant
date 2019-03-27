"""The `statistics` module.

Helpful statistical models and indicators.

"""

from math import sqrt

import numpy as np
import pandas as pd


class Ema:
    """An exponential moving average.

    Args:
        half_life (float): The half life of samples passed to `step`.

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
        self.__value = self.__a * self.__value + (1-self.__a) * value
        self.__samples_needed = max(0, self.__samples_needed - 1)

    @property
    def ready(self):
        return self.__samples_needed == 0


class GaussianError(Exception):
    pass


class Gaussian:
    '''Single or multi-variate gaussian.

    For multi-variate gaussians, set the mean and variance to NumPy arrays or Pandas series. The
    dimension/type of mean and variance should match.

    TODO: Write tests (esp. for multivariate case).

    Args:
        mean: The mean of the Gaussian. Should be a numerical scalar, list, NumPy array, or Pandas
            series. Scalars and lists are marshalled to/from NumPy as necessary, and integers are
            treated as floats.
        covariance: The covariance matrix of the Gaussian (can also be a scalar in the 1D case or
            a list/array/series of variances in the uncorrelated case).

    '''

    def __init__(self, mean, covariance):
        # Marshal non-NumPy/Pandas types into NumPy.
        if type(mean) == float or type(mean) == int:
            mean = np.asarray([mean])
            covariance = np.diag([covariance])
        elif type(mean) == list:
            mean = np.asarray(mean)
            covariance = np.asarray(covariance)

        # Convert a vector of variances into a covariance matrix.
        if len(covariance.shape) == 1:
            covariance = np.diag(covariance)
        if np.shape(covariance) != (np.size(mean), np.size(mean)):
            raise GaussianError('mean and covariance have mismatched dimension')

        self._mean = mean
        self._covariance = covariance

    @property
    def mean(self):
        if self._mean.size == 1:
            return np.asscalar(np.asarray(self._mean))
        return self._mean

    @property
    def covariance(self):
        if self._covariance.size == 1:
            return np.asscalar(np.asarray(self._covariance))
        return self._covariance

    @property
    def variance(self):
        if self._covariance.size == 1:
            return self.covariance
        return np.diag(self._covariance)

    @property
    def stddev(self):
        return np.sqrt(self.variance)

    @staticmethod
    def sum(xs):
        '''Sum of many i.i.d. Gaussian variables.

        Args:
            xs (list): A list of Gaussians.

        '''
        return Gaussian(np.sum([x._mean for x in xs], axis=0),
                        np.sum([x._covariance for x in xs], axis=0))

    @staticmethod
    def fuse(xs):
        '''Fuses many Gaussian distributions in the same space by multiplying (and then normalizing)
        their PDFs. This is used e.g. in computing the new state of a Kalman filter.

        TODO: Vectorize this (no iterative `and`).
        TODO: Check that input observations make sense.

        Args:
            xs (list): A list of Gaussians.

        Examples:
            Input: Gaussian.join([Gaussian(3,5), Gaussian(4,15), Gaussian(5,25)])
            Output: Gaussian(3.4782608695652177, 3.260869565217391)

            Input: Gaussian.join([])
            Output: Gaussian([], [])

        '''

        if len(xs) == 0:
            return Gaussian([], [])

        acc = xs[0]
        for x in xs[1:]:
            acc = acc & x
        return acc

    def __and__(self, x):
        '''Binary operator version of `fuse`.

        Requires only one inverse via formula here: https://math.stackexchange.com/a/964103.

        '''
        sum_inv = np.linalg.inv(self._covariance + x._covariance)
        covariance = self._covariance @ sum_inv @ x._covariance
        mean = x._covariance @ sum_inv @ self._mean + self._covariance @ sum_inv @ x._mean
        return Gaussian(mean, covariance)

    def __add__(self, scalar):
        '''Add a scalar to the Gaussian. For the sum of i.i.d. Gaussians see `sum`.'''
        return Gaussian(self._mean + scalar, self._covariance)

    def __sub__(self, x):
        return self + -x

    def __mul__(self, scalar):
        '''Scalar multiplication. For the product of two PDFs see `__and__`, and for the product of
        two i.i.d. variables see __matmul__.'''
        return Gaussian(self._mean * scalar, self._covariance * scalar * scalar)

    def __div__(self, scalar):
        return self * (1 / scalar)

    def __matmul__(self, x):
        '''Multiplication of two i.i.d. Gaussian variables. The result is NOT Gaussian but we return
        a Gaussian approximation with the same mean and covariance.'''
        mean = self._mean * x._mean
        covariance = ((self._covariance + x._mean * x._mean)
                      * (x._covariance + self._mean * self._mean)
                      - (self._mean * self._mean * x._mean * x._mean))
        return Gaussian(mean, covariance)

    def __repr__(self):
        return 'Gaussian({}, {})'.format(self.mean, self.covariance)
