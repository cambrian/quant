"""
Mathematical functions. Named `maths` instead of `math` to avoid collision with the builtin math
module.
"""
import numpy as np
import pandas as pd
# pylint bug
# pylint: disable=no-name-in-module
from scipy.special import expit


def orthogonal_projection(a, b):
    """
    Project `a` onto the vector `b`.

    >>> orthogonal_projection(np.array([1, 0]), np.array([1, 1]))
    array([0.5, 0.5])

    >>> orthogonal_projection(np.array([1, 1]), np.array([1, 0]))
    array([1., 0.])

    """
    b = np.array(b)
    dims = len(np.shape(a))
    assert dims in (1, 2)
    s = a @ b / np.sum(b * b)
    if dims == 2:
        result = b * s[:, np.newaxis]
        if isinstance(a, pd.DataFrame):
            return pd.DataFrame(result, index=a.index, columns=a.columns)
        return result
    result = s * b
    if isinstance(a, pd.Series):
        return pd.Series(result, index=a.index)
    return result


def hyperplane_projection(a, b):
    """Project `a` onto the origin-centered hyperplane described by normal vector `b`."""
    return a - orthogonal_projection(a, b)


def sigmoid(x):
    """
    Friendlier name for the sigmoid function.

    >>> sigmoid(0)
    0.5

    >>> sigmoid(np.array([0,1]))
    array([0.5       , 0.73105858])


    >>> sigmoid(pd.Series([0,1]))
    0    0.500000
    1    0.731059
    dtype: float64

    """
    return expit(x)
