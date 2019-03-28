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
        self.__value = self.__a * self.__value + (1 - self.__a) * value
        self.__samples_needed = max(0, self.__samples_needed - 1)

    @property
    def ready(self):
        return self.__samples_needed == 0


class GaussianError(Exception):
    pass


class Gaussian:
    """Single or multi-variate Gaussian.

    For multi-variate Gaussians, set the mean and variance to NumPy arrays or Pandas series. The
    dimension/type of mean and variance should match.

    Args:
        mean: The mean of the Gaussian. Should be a numerical scalar, list, NumPy array, or Pandas
            series. Scalars and lists are marshalled to/from NumPy as necessary, and integers are
            treated as floats.
        covariance: The covariance matrix of the Gaussian (can also be a scalar in the 1D case or
            a list/array/series of variances in the uncorrelated case).

    >>> Gaussian(1, 1)
    Gaussian:
    mean:
    1
    covariance:
    1

    >>> Gaussian([1, 1], [1, 1])
    Gaussian:
    mean:
    [1 1]
    covariance:
    [[1 0]
     [0 1]]

    >>> Gaussian([1, 1], [[1, 0], [0, 1]])
    Gaussian:
    mean:
    [1 1]
    covariance:
    [[1 0]
     [0 1]]

    >>> Gaussian([1, 1], np.array([[1, 0], [0, 1]]))
    Gaussian:
    mean:
    [1 1]
    covariance:
    [[1 0]
     [0 1]]

    >>> Gaussian(pd.Series([1, 1]), pd.Series([1, 1]))
    Gaussian:
    mean:
    0    1
    1    1
    dtype: int64
    covariance:
       0  1
    0  1  0
    1  0  1

    """

    def __init__(self, mean, covariance):
        # Marshal non-NumPy/Pandas types into NumPy.
        if len(np.shape(mean)) == 0:
            mean = np.array([mean])
            covariance = np.array([covariance])
        elif isinstance(mean, list):
            mean = np.array(mean)
            covariance = np.array(covariance)

        # Convert a vector of variances into a covariance matrix.
        if len(covariance.shape) == 1:
            covariance = np.diag(covariance)

        # Keep index names in covariance if using Pandas.
        if isinstance(mean, pd.Series):
            covariance = pd.DataFrame(covariance, index=mean.index, columns=mean.index)

        if np.shape(covariance) != (np.size(mean), np.size(mean)):
            raise GaussianError("mean and covariance have mismatched dimension")

        self.__mean = mean
        self.__covariance = covariance

    @property
    def mean(self):
        """
        >>> Gaussian(1, 0).mean
        1

        >>> Gaussian(pd.Series([2]), pd.DataFrame([1])).mean
        2

        """
        if self.__mean.size == 1:
            return np.asscalar(self.__mean)
        return self.__mean

    @property
    def covariance(self):
        """
        >>> Gaussian(1, 0).covariance
        0

        >>> Gaussian(pd.Series([2]), pd.DataFrame([1])).covariance
        1

        """
        if self.__covariance.size == 1:
            # The call to `np.array` is necessary when the covariance is a DataFrame with a single
            # entry (see doctest example).
            return np.asscalar(np.array(self.__covariance))
        return self.__covariance

    @property
    def variance(self):
        if self.__covariance.size == 1:
            return self.covariance
        return np.diag(self.__covariance)

    @property
    def stddev(self):
        return np.sqrt(self.variance)

    @staticmethod
    def sum(xs):
        """Sum of many i.i.d. Gaussian variables or scalars.

        Args:
            xs (list): A list of Gaussians.

        >>> Gaussian.sum([Gaussian(3, 5), Gaussian(4, 15), Gaussian(5, 25)])
        Gaussian:
        mean:
        12
        covariance:
        45

        >>> Gaussian.sum([ \
                Gaussian(pd.Series([1, 1], index=['a', 'b']), pd.Series([1, 1], index=['a', 'b'])), \
                Gaussian(pd.Series([1, 1], index=['a', 'b']), pd.Series([1, 1], index=['a', 'b'])) \
            ])
        Gaussian:
        mean:
        a    2
        b    2
        dtype: int64
        covariance:
           a  b
        a  2  0
        b  0  2

        """
        if len(xs) == 0:
            return Gaussian([], [])

        acc = xs[0]
        for x in xs[1:]:
            acc = acc + x
        return acc

    @staticmethod
    def intersect(xs):
        """Computes an intersection of many Gaussian distributions in the same space by multiplying
        (and then normalizing) their PDFs.

        This is used e.g. in computing the new state of a Kalman filter.

        TODO: Vectorize this (no iterative `and`).
        TODO: Check that input observations make sense.

        Args:
            xs (list): A list of Gaussians.

        >>> Gaussian.intersect([Gaussian(3, 5), Gaussian(4, 15), Gaussian(5, 25)])
        Gaussian:
        mean:
        3.4782608695652177
        covariance:
        3.260869565217391

        >>> Gaussian.intersect([])
        Gaussian:
        mean:
        []
        covariance:
        []

        >>> Gaussian.intersect([Gaussian(1,1)])
        Gaussian:
        mean:
        1
        covariance:
        1

        """
        if len(xs) == 0:
            return Gaussian([], [])

        acc = xs[0]
        for x in xs[1:]:
            acc = acc & x
        return acc

    def __and__(self, x):
        """Binary operator version of `intersect`.

        Requires only one inverse via formula here: https://math.stackexchange.com/a/964103.

        >>> Gaussian(pd.Series([1, 1], index=['a', 'b']), pd.Series([1, 1], index=['a', 'b'])) \
            & Gaussian(pd.Series([1, 1], index=['a', 'b']), pd.Series([1, 1], index=['a', 'b']))
        Gaussian:
        mean:
        a    1.0
        b    1.0
        dtype: float64
        covariance:
             a    b
        a  0.5  0.0
        b  0.0  0.5

        >>> Gaussian(pd.Series([1, 1]), pd.Series([1, 1])) \
            & Gaussian(pd.Series([1, 1]), pd.Series([1, 1]))
        Gaussian:
        mean:
        0    1.0
        1    1.0
        dtype: float64
        covariance:
             0    1
        0  0.5  0.0
        1  0.0  0.5

        """
        sum_inv = np.linalg.inv(self.__covariance + x.__covariance)
        if isinstance(x.__covariance, pd.DataFrame):
            sum_inv = pd.DataFrame(
                sum_inv, index=self.__covariance.index, columns=self.__covariance.columns
            )
        covariance = self.__covariance @ sum_inv @ x.__covariance
        mean = x.__covariance @ sum_inv @ self.__mean + self.__covariance @ sum_inv @ x.__mean
        return Gaussian(mean, covariance)

    def __add__(self, x):
        """Add a scalar or another Gaussian to the Gaussian.

        >>> Gaussian([1, 1], [[1, 2], [3, 4]]) + 3
        Gaussian:
        mean:
        [4 4]
        covariance:
        [[1 2]
         [3 4]]

        >>> Gaussian([1, 1], [[1, 2], [3, 4]]) + Gaussian([1, 1], [[1, 2], [3, 4]])
        Gaussian:
        mean:
        [2 2]
        covariance:
        [[2 4]
         [6 8]]

        """
        if isinstance(x, Gaussian):
            return Gaussian(self.__mean + x.__mean, self.__covariance + x.__covariance)
        return Gaussian(self.__mean + x, self.__covariance)

    def __sub__(self, x):
        """
        >>> Gaussian([1, 1], [[1, 2], [3, 4]]) - 1
        Gaussian:
        mean:
        [0 0]
        covariance:
        [[1 2]
         [3 4]]
        """
        return self + -x

    def __mul__(self, s):
        """Scalar multiplication. `s` may be a scalar or 1D vector.

        For the product of two PDFs see `__and__`, and for the product of two i.i.d. variables
        see `__matmul__`.

        >>> Gaussian([1, 1], [1, 1]) * [1, 2]
        Gaussian:
        mean:
        [1 2]
        covariance:
        [[1 0]
         [0 4]]

        """
        # Marshal non-NumPy/Pandas types into NumPy.
        if len(np.shape(s)) == 0:
            s = np.array([s])
        elif type(s) == list:
            s = np.array(s)
        s_diag = np.diag(s)
        return Gaussian(self.__mean * s, self.__covariance * s_diag * s_diag)

    def __truediv__(self, s):
        """Scalar division. `s` may be a scalar or 1D vector.

        >>> Gaussian([1, 2], [1, 2]) / 2
        Gaussian:
        mean:
        [0.5 1. ]
        covariance:
        [[0.25 0.  ]
         [0.   0.5 ]]

        >>> Gaussian([1, 2], [1, 2]) / [1, 2]
        Gaussian:
        mean:
        [1. 1.]
        covariance:
        [[1.  0. ]
         [0.  0.5]]

        """
        # Marshal non-NumPy/Pandas types into NumPy.
        if len(np.shape(s)) == 0:
            s = np.array([s])
        elif type(s) == list:
            s = np.array(s)
        return self * (1 / s)

    def __div__(self, s):
        return self.__truediv__(s)

    def __matmul__(self, x):
        """Multiplication of two i.i.d. Gaussian variables. The result is NOT Gaussian but we return
        a Gaussian approximation with the same mean and covariance.

        As a reminder, we have Var(XY) = (Var(X) + E[X]^2) * (Var(Y) + E[Y]^2) - E[X]^2 * E[Y]^2
        and E[XY] = E[X] * E[Y] for (X, Y) independent.

        NOTE: If the Gaussians are multivariate, `__matmul__` computes a point-wise result for each
        dimension. This result makes no sense if either covariance matrix is non-diagonal.

        """
        mean = self.__mean * x.__mean
        covariance = (self.__covariance + x.__mean * x.__mean) * (
            x.__covariance + self.__mean * self.__mean
        ) - (self.__mean * self.__mean * x.__mean * x.__mean)
        return Gaussian(mean, covariance)

    def __repr__(self):
        return "Gaussian:\nmean:\n{}\ncovariance:\n{}".format(self.mean, self.covariance)
