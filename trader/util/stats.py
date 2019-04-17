"""The `statistics` module.

Helpful statistical models and indicators.

"""

import itertools

import numpy as np
import pandas as pd
from pandas.core.indexes.range import RangeIndex
from scipy.spatial.distance import mahalanobis
from scipy.special import binom as choose
from scipy.stats import multivariate_normal


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


def _is_labeled(x):
    if isinstance(x, pd.Series):
        return not isinstance(x.index, RangeIndex)
    elif isinstance(x, pd.DataFrame):
        return not isinstance(x.columns, RangeIndex)
    return False


class GaussianError(Exception):
    pass


class Gaussian:
    """Single or multi-variate Gaussian."""

    def __init__(self, mean, covariance):
        """
        For multi-variate Gaussians, set the mean and variance to NumPy arrays or Pandas series. The
        dimension/type of mean and variance should match.

        Args:
            mean: The mean of the Gaussian. Should be a numerical scalar, list, NumPy array, or
                Pandas series. Scalars and lists are marshalled to/from NumPy as necessary, and
                integers are treated as floats.
            covariance: The covariance matrix of the Gaussian (can also be a scalar in the 1D case
                or a list/array/series of variances in the uncorrelated case).

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

        >>> Gaussian(pd.Series([1, 1]), [1, 1])
        Gaussian:
        mean:
        0    1
        1    1
        dtype: int64
        covariance:
           0  1
        0  1  0
        1  0  1

        >>> Gaussian([1, 1], pd.DataFrame([[1, 1]], index=['a', 'b']))
        Traceback (most recent call last):
        stats.GaussianError: covariance column labels and index labels do not match

        >>> Gaussian(pd.Series([1, 1], index=['a', 'b']), pd.Series([1, 1]))
        Traceback (most recent call last):
        stats.GaussianError: mean labels and covariance labels do not match

        >>> Gaussian(pd.Series([1, 1], index=['b', 'a']), [1, 1])
        Gaussian:
        mean:
        b    1
        a    1
        dtype: int64
        covariance:
           b  a
        b  1  0
        a  0  1

        """
        # Marshal non-NumPy/Pandas types into NumPy.
        if len(np.shape(mean)) == 0:
            mean = np.array([mean])
        elif isinstance(mean, list):
            mean = np.array(mean)
        if len(np.shape(covariance)) == 0:
            covariance = np.array([[covariance]])
        elif isinstance(covariance, list):
            covariance = np.array(covariance)

        # Convert a vector of variances into a covariance matrix.
        if len(np.shape(covariance)) == 1:
            covariance_matrix = np.diag(covariance)
            if isinstance(covariance, pd.Series):
                index = covariance.index
                covariance = pd.DataFrame(covariance_matrix, columns=index, index=index)
            else:
                covariance = covariance_matrix

        # Ensure internal consistency of covariance labels.
        if isinstance(covariance, pd.DataFrame):
            if list(covariance.columns) != list(covariance.index):
                raise GaussianError("covariance column labels and index labels do not match")

        # Ensure consistency of labels between means and covariances.
        if isinstance(mean, pd.Series):
            if isinstance(covariance, pd.DataFrame):
                if list(mean.index) != list(covariance.index):
                    raise GaussianError("mean labels and covariance labels do not match")
            else:
                index = mean.index
                covariance = pd.DataFrame(covariance, columns=index, index=index)
        elif isinstance(covariance, pd.DataFrame):
            index = covariance.index
            mean = pd.Series(mean, index=index)

        # Sanity check dimensions after pre-processing.
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

        >>> Gaussian.intersect([Gaussian(1, 1)])
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

        >>> Gaussian(pd.Series([1, 2], index=['a', 'b']), pd.DataFrame([ \
                [2, -1], \
                [-1, 2] \
            ], index=['a', 'b'], columns=['a', 'b'])) \
            & Gaussian(pd.Series([4, 3], index=['b', 'a']), pd.Series([1, 1], index=['b', 'a']))
        Gaussian:
        mean:
        a    2.0
        b    3.0
        dtype: float64
        covariance:
               a      b
        a  0.625 -0.125
        b -0.125  0.625

        >>> Gaussian(pd.Series([1], index=['a']), 1) & Gaussian(pd.Series([2], index=['b']), 2)
        Gaussian:
        mean:
        a    1.0
        b    2.0
        dtype: float64
        covariance:
             a    b
        a  1.0  0.0
        b  0.0  2.0

        >>> Gaussian(pd.Series([1, 2, 1], index=['a', 'd', 'b']), pd.DataFrame([ \
                [2, 1, -1], \
                [1, 2, 1], \
                [-1, 1, 2] \
            ], index=['a', 'd', 'b'], columns=['a', 'd', 'b'])) \
            & Gaussian(pd.Series([3, 2, 3], index=['a', 'd', 'c']), \
                pd.Series([1, 1, 1], index=['a', 'd', 'c']))
        Gaussian:
        mean:
        a    2.250000e+00
        b    1.054712e-15
        c    3.000000e+00
        d    2.250000e+00
        dtype: float64
        covariance:
               a         b    c      d
        a  0.625 -0.500002  0.0  0.125
        b -0.500  1.000000  0.0  0.500
        c  0.000  0.000000  1.0  0.000
        d  0.125  0.499998  0.0  0.625

        """
        # Check if Pandas-based Gaussians have variables not in common, complicating intersection.
        if _is_labeled(self.__mean) and _is_labeled(x.__mean):
            union = self.__mean.index.union(x.__mean.index)
            not_in_s = x.__mean.index.difference(self.__mean.index)
            not_in_x = self.__mean.index.difference(x.__mean.index)

            # Some variables are disjoint. Fill in zero-means and large variances for the
            # variables not present in each Gaussian, then compute the intersection as normal.
            if not (not_in_s.empty and not_in_x.empty):
                s1_mean = pd.Series(0, index=union).add(self.__mean, fill_value=0)
                x1_mean = pd.Series(0, index=union).add(x.__mean, fill_value=0)
                # Can't just set `diag_elem` to 1e100 because the pseudoinverse calculation runs
                # into numerical instability. Instead, we ensure that the fill element scales
                # with the (summed) matrix norms of each covariance.
                diag_elem = 1e10 * (
                    np.linalg.norm(self.__covariance) + np.linalg.norm(x.__covariance)
                )
                s1_cov = pd.DataFrame(0, index=union, columns=union).add(
                    self.__covariance, fill_value=0
                )
                x1_cov = pd.DataFrame(0, index=union, columns=union).add(
                    x.__covariance, fill_value=0
                )
                for i in not_in_s:
                    s1_cov.loc[i, i] = diag_elem
                for i in not_in_x:
                    x1_cov.loc[i, i] = diag_elem
                return Gaussian(s1_mean, s1_cov) & Gaussian(x1_mean, x1_cov)

        # Sort `x` labels to match `mean` indexing.
        if self.__has_similar_labels(x.__mean):
            x_mean = x.__mean[self.__mean.index]
            x_covariance = x.__covariance[self.__mean.index]
        else:
            x_mean = x.__mean
            x_covariance = x.__covariance

        sum_inv = np.linalg.pinv(self.__covariance + x_covariance)
        if isinstance(self.__mean, pd.Series):
            sum_inv = pd.DataFrame(sum_inv, index=self.__mean.index, columns=self.__mean.index)
        covariance = self.__covariance @ sum_inv @ x_covariance
        mean = x_covariance @ sum_inv @ self.__mean + self.__covariance @ sum_inv @ x_mean
        return Gaussian(mean, covariance)

    def __add__(self, x):
        """Adds a scalar or another Gaussian to the Gaussian.

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

        >>> Gaussian([1, 1], [1, 1]) * 2
        Gaussian:
        mean:
        [2 2]
        covariance:
        [[4 0]
         [0 4]]

        >>> Gaussian(pd.Series([1, 1]), [1, 1]) * 2
        Gaussian:
        mean:
        0    2
        1    2
        dtype: int64
        covariance:
           0  1
        0  4  0
        1  0  4

        >>> Gaussian([1, 1], [1, 1]) * [1, 2]
        Gaussian:
        mean:
        [1 2]
        covariance:
        [[1 0]
         [0 4]]

        >>> Gaussian(pd.Series([1, 1], index=['a', 'b']), [[1, 1], [1, 1]]) * pd.Series([2, 1], \
            index=['b', 'a'])
        Gaussian:
        mean:
        a    1
        b    2
        dtype: int64
        covariance:
           a  b
        a  1  2
        b  2  4

        """
        if type(s) == list:
            s = np.array(s)
        if len(np.shape(s)) == 1:
            if self.__has_similar_labels(s):
                s = s[self.__mean.index]
            return Gaussian(self.__mean * s, self.__covariance * s[:, None] * s[None, :])
        return Gaussian(self.__mean * s, self.__covariance * s * s)

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
        if type(s) == list:
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

    def pdf(self, x):
        """Evaluates the PDF of this Gaussian at `x`.

        NOTE: Ensure that the Gaussian covariance is positive semi-definite.

        >>> Gaussian(1, 1).pdf(1)
        0.3989422804014327

        >>> Gaussian(1, 1).pdf([1, 2, 3])
        array([0.39894228, 0.24197072, 0.05399097])

        >>> Gaussian([1, 1], [[1, 0], [0, 1]]).pdf([1, 1])
        0.15915494309189535

        >>> Gaussian(1, 1).pdf(pd.DataFrame([1, 2, 3]))
        0    0.398942
        1    0.241971
        2    0.053991
        dtype: float64

        >>> Gaussian(1, 1).pdf(pd.Series([1, 2, 3]))
        array([0.39894228, 0.24197072, 0.05399097])

        >>> Gaussian([0, 0, 0], [1, 1, 1]).pdf(pd.Series([1, 1, 1]))
        0.014167345154413284

        """
        # Sort `x` labels to match `mean` indexing.
        if self.__has_similar_labels(x):
            x = x[self.__mean.index]

        # Consider pre-computing and storing this distribution on the Gaussian.
        distribution = multivariate_normal(self.mean, self.covariance, allow_singular=True)
        result = distribution.pdf(x)

        if isinstance(x, pd.DataFrame):
            return pd.Series(result, index=x.index)
        return result

    def cdf(self, a, b=None):
        """Computes P(X < `a`) for X distributed like this Gaussian.

        If `b` is also specified, this function will compute P(`a` < X < `b`).

        For multivariate Gaussians, this function performs inclusion-exclusion on (2 ^ N) CDF
        results, which computes the hypercubic intersection between CDF(upper limit) and CDF(lower
        limit). In the 2D case between points (a, b) and (c, d), where a < c and b < d, this works
        out to CDF(c, d) - CDF(b, d) - CDF(a, c) + CDF(a, b).

        NOTE: Ensure that the Gaussian covariance is positive semi-definite.

        TODO: Figure out how to use `mvnormcdf` from `statsmodels` for more efficient multivariate
        CDF intervals via sampling. Although their code looks sus...

        >>> Gaussian(1, 9).cdf(4)
        0.841344746068543

        >>> Gaussian(1, 9).cdf([4, 1])
        array([0.84134475, 0.5       ])

        >>> Gaussian(0, 1).cdf(-1, 1)
        0.6826894921370861

        >>> Gaussian(0, 1).cdf([-1, -2], [1, 2])
        array([0.68268949, 0.95449974])

        Output is slightly non-deterministic:
        >>> Gaussian(pd.Series([0, 0, 0]), pd.DataFrame([ \
                [ 2, -1,  0], \
                [-1,  2, -1], \
                [ 0, -1,  2] \
            ])).cdf([ \
                [0, 0, 0], \
                [-4, -2, -3] \
            ], [ \
                [1, 1, 1], \
                [1, 2, 4] \
            ]).round(3)
        array([0.017, 0.644])

        >>> Gaussian(pd.Series([0, 2], index=['a', 'b']), [1, 1]) \
                .cdf(pd.Series([2, 0], index=['b', 'a']))
        0.25

        """
        # Consider pre-computing and storing this distribution on the Gaussian.
        distribution = multivariate_normal(self.mean, self.covariance, allow_singular=True)

        if self.__should_vectorize(a):
            if b is None:
                b = np.empty(np.shape(a), dtype=object)
            if isinstance(a, pd.DataFrame):
                b = pd.DataFrame(b)
                b.columns, b.index = a.columns, a.index
                result = np.array([self.cdf(a.iloc[i], b.iloc[i]) for i in a.index])
            else:
                result = np.array([self.cdf(a[i], b[i]) for i in range(len(a))])

            # Restore row labels as necessary.
            if isinstance(a, pd.DataFrame) or isinstance(a, pd.Series):
                return pd.Series(result, index=a.index)
            return result
        elif b is None:
            # Sort `a` labels to match `mean` indexing.
            if self.__has_similar_labels(a):
                a = a[self.__mean.index]
            return distribution.cdf(a)
        # Multivariate intervals require a non-degenerate hypercube.
        elif np.any(np.array(b) - np.array(a) <= 0):
            return 0
        # Apply inclusion-exclusion (see function header) to compute multivariate intervals.
        else:
            # Sort `a` labels to match `mean` indexing.
            if self.__has_similar_labels(a):
                a = a[self.__mean.index]
            # Sort `b` labels to match `mean` indexing.
            if self.__has_similar_labels(b):
                b = b[self.__mean.index]

            num_vars = len(self.__mean)
            # Returns e.g. [[0, 0], [0, 1], [1, 0], [1, 1]] for 2 variables. More generally, this
            # returns the (2 ^ N) bit vectors of length N, sorted ascending by the number of ones.
            inclusion_bits = np.array(
                sorted(list(itertools.product([0, 1], repeat=num_vars)), key=sum)
            ).astype(bool)

            i = 0
            result = 0
            multiplier = 1

            # Iterates through `inclusion_bits` grouped by the number of ones `num_upper` in the bit
            # vector. At each value of `num_upper`, there are (`num_vars` choose `num_upper`) such
            # elements in `inclusion_bits`.
            for num_upper in range(num_vars + 1):
                for _ in range(int(choose(num_vars, num_upper))):
                    # If `inclusion_bits[i]` is e.g. 1001, we will construct a CDF limit by taking
                    # the first variable from `b`, the second and third variables from `a`, and the
                    # fourth variable from `b`.
                    inclusion_exclusion = np.where(inclusion_bits[i], a, b)
                    result += multiplier * distribution.cdf(inclusion_exclusion)
                    i += 1
                # This corresponds to switching the power of (-1) in the standard formula for
                # computing inclusion-exclusion.
                multiplier *= -1
            return result

    def z_score(self, x):
        """Computes the Mahalanobis distance of `x` from the center of this Gaussian. In the 1D case
        this reduces to computing an absolute z-score.

        NOTE: This function is vectorized if you pass multiple points as `x`.

        >>> Gaussian(2, 4).z_score(6)
        2.0

        >>> Gaussian(2, 4).z_score([0, 3, 6])
        array([1. , 0.5, 2. ])

        >>> Gaussian(pd.Series([2, 0, 0]), pd.DataFrame([ \
                [ 1.5, -0.5, -0.5], \
                [-0.5,  1.5, -0.5], \
                [-0.5, -0.5,  1.5] \
            ])).z_score(pd.Series([0, 1, 0]))
        1.7320508075688763

        >>> Gaussian(pd.Series([2, 0, 0]), pd.DataFrame([ \
                [ 1.5, -0.5, -0.5], \
                [-0.5,  1.5, -0.5], \
                [-0.5, -0.5,  1.5] \
            ])).z_score([[0, 1, 0], [1, 0, 0]])
        array([1.73205081, 1.        ])

        >>> Gaussian(pd.Series([0, 1], index=['a', 'b']), [1, 2]).z_score([1, 3])
        1.7320508075688772

        >>> Gaussian(pd.Series([0, 1], index=['a', 'b']), [1, 2]) \
                .z_score(pd.DataFrame([[3, 1], [5, 2]], columns=['b', 'a'], index=[0, 1]))
        0    1.732051
        1    3.464102
        dtype: float64

        """
        if self.__should_vectorize(x):
            if isinstance(x, pd.DataFrame):
                cov_inv = np.linalg.pinv(self.__covariance)
                x = x[self.__mean.index]
                return x.apply(lambda x: mahalanobis(self.__mean, x, cov_inv), axis=1)
            else:
                return np.array([self.z_score(x_i) for x_i in x])
        else:
            # Sort `x` labels to match `mean` indexing.
            if self.__has_similar_labels(x):
                x = x[self.__mean.index]
            return mahalanobis(self.__mean, x, np.linalg.pinv(self.__covariance))

    def gradient(self, x):
        """
        >>> Gaussian([1, 1], [1, 1]).gradient([0, 0])
        array([0.05854983, 0.05854983])

        >>> Gaussian(pd.Series([1, 1]), [1, 2]).gradient([0, 0])
        0    0.05316
        1    0.02658
        dtype: float64

        >>> Gaussian(pd.Series([1, 1]), [1, 2]).gradient(pd.DataFrame([[0, 0], [0, 1]]))
                  0        1
        0  0.053160  0.02658
        1  0.068259  0.00000

        >>> Gaussian(pd.Series([1, 1], index=['a', 'b']), [1, 2]) \
            .gradient(pd.DataFrame([[0, 0], [1, 0]], columns=['b', 'a'], index=[0, 1]))
                 b         a
        0  0.02658  0.053160
        1  0.00000  0.068259

        """
        if self.__should_vectorize(x):
            if isinstance(x, pd.DataFrame):
                result = np.array([self.gradient(x.iloc[i]) for i in x.index])
            else:
                result = np.array([self.gradient(x_i) for x_i in x])

            # Restore row labels as necessary.
            if isinstance(x, pd.DataFrame):
                return pd.DataFrame(result, columns=x.columns, index=x.index)
            elif isinstance(x, pd.Series):
                return pd.Series(result, index=x.index)
            return result
        else:
            # Sort `x` labels to match `mean` indexing.
            if self.__has_similar_labels(x):
                x_index_saved = x.index
                x = x[self.__mean.index]

            cov_inv = np.linalg.pinv(self.__covariance)
            if isinstance(self.__covariance, pd.DataFrame):
                index = self.__covariance.index
                cov_inv = pd.DataFrame(cov_inv, columns=index, index=index)
            result = -self.pdf(x) * cov_inv @ (x - self.__mean)

            # Restore old indexing of `x` as necessary.
            if self.__has_similar_labels(x):
                return result[x_index_saved]
            return result

    def __has_similar_labels(self, x):
        if _is_labeled(self.__mean) and _is_labeled(x):
            if isinstance(x, pd.DataFrame):
                return set(x.columns) == set(self.__mean.index)
            elif isinstance(x, pd.Series):
                return set(x.index) == set(self.__mean.index)
        return False

    def __should_vectorize(self, points):
        return len(np.shape(points)) > len(np.shape(self.mean))

    def __getitem__(self, x):
        return Gaussian(self.__mean[x], self.__covariance.loc[x, x])

    def __repr__(self):
        return "Gaussian:\nmean:\n{}\ncovariance:\n{}".format(self.mean, self.covariance)
