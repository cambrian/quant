import numpy as np
import pandas as pd
import pytest
from numpy_ringbuffer import RingBuffer
from scipy.spatial import distance
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.vector_ar.vecm import coint_johansen

from research.strategy.base import Strategy
from trader.util.linalg import hyperplane_projection, orthogonal_projection
from trader.util.stats import Gaussian


def johansen(P, maxlag):
    """
    Returns the statistically-significant cointegrating vectors in P (normalized to unit vectors),
    as well as the mean values of P.
    """
    mean = P.mean()
    c = coint_johansen(P / mean - 1, det_order=-1, k_ar_diff=maxlag)
    significant_results = (c.lr1 > c.cvt[:, 1]) * (c.lr2 < c.cvm[:, 2])
    Q = pd.DataFrame(c.evec[:, significant_results].T, columns=P.columns)
    return mean, Q.div(Q.apply(np.linalg.norm, axis=1), axis=0)


# TODO: reimplement with vector autoregression test, similar to johansen internals.
@pytest.mark.skip(reason="not a test of functionality")
def test_coint(P, mean_train, q, maxlag):
    x = (P / mean_train - 1) @ q
    return adfuller(x, regression="nc", maxlag=maxlag, autolag=None)[1]


def cosine_similar_to_any(Q, x):
    for q in Q:
        if distance.cosine(q, x) < 0.1:
            return True
    return False


class Cointegrator(Strategy):
    def __init__(self, train_size, validation_size, cointegration_period, maxlag):
        self.window_size = train_size + validation_size
        self.train_size = train_size
        self.validation_size = validation_size
        self.cointegration_period = cointegration_period
        self.maxlag = maxlag
        self.sample_counter = 0
        self.price_history = None
        self.base_prices = None
        self.base_cov = None
        self.prev_prediction = None
        self.coints = []

    def tick(self, frame):
        prices = frame["price"]

        if self.price_history is None:
            self.price_history = RingBuffer(self.window_size, dtype=(np.float64, len(prices.index)))

        if self.prev_prediction is None:
            self.prev_prediction = self.null_estimate(frame)

        self.price_history.append(prices)

        if len(self.price_history) < self.window_size:
            return self.null_estimate(frame)

        if self.sample_counter == 0:
            P = pd.DataFrame(self.price_history, columns=prices.index)
            P_train = P.iloc[: self.train_size]
            P_val = P.iloc[self.train_size :]
            mean, candidates = johansen(P_train, self.maxlag)
            self.base_prices = mean
            new_coints = [
                q for q in candidates.values if test_coint(P_val, mean, q, self.maxlag) < 0.05
            ]
            old_coints = [
                q
                for q in self.coints
                if test_coint(P_val, mean, q, self.maxlag) < 0.05
                and not cosine_similar_to_any(new_coints, q)
            ]
            self.coints = new_coints + old_coints
            self.base_cov = P.cov()

        self.sample_counter -= 1
        self.sample_counter %= self.cointegration_period

        if not self.coints:
            return self.null_estimate(frame)

        fair_means = [
            (hyperplane_projection(prices / self.base_prices - 1, q) + 1) * self.base_prices
            for q in self.coints
        ]
        fair = Gaussian.intersect([Gaussian(mean, self.base_cov) for mean in fair_means])
        return fair
