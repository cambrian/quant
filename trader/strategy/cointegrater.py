import numpy as np
import pandas as pd
from numpy_ringbuffer import RingBuffer
from statsmodels.tsa.vector_ar.vecm import coint_johansen

from research.strategy.base import Strategy
from trader.util.linalg import hyperplane_projection, orthogonal_projection
from trader.util.stats import Gaussian


class Cointegrator(Strategy):
    def __init__(self, window_size, cointegration_frequency=4):
        self.window_size = window_size
        self.cointegration_period = window_size // cointegration_frequency
        self.sample_counter = 0
        self.price_history = None
        self.A = None
        self.base_prices = None
        self.covs = None

    def step(self, frame):
        prices = frame["price"]

        if self.price_history is None:
            self.price_history = RingBuffer(self.window_size, dtype=(np.float64, len(prices.index)))

        self.price_history.append(prices)

        if len(self.price_history) < self.window_size:
            return self.null_estimate(prices)

        if self.sample_counter == 0:
            P = pd.DataFrame(self.price_history, columns=prices.index)
            self.base_prices = P.mean()
            P_norm = P - self.base_prices

            c = coint_johansen(P_norm, det_order=-1, k_ar_diff=1)

            significant_results = (c.lr1 > c.cvt[:, 1]) * (c.lr2 < c.cvm[:, 2])
            if np.any(significant_results):
                self.A = pd.DataFrame(c.evec[:, significant_results].T, columns=prices.index)
                self.covs = [
                    hyperplane_projection(P_norm, a).cov() * 2 + P.cov() for a in self.A.values
                ]
            else:
                self.A = None
                self.covs = None

        self.sample_counter -= 1
        self.sample_counter %= self.cointegration_period

        if self.A is None:
            return self.null_estimate(prices)

        prices_norm = prices - self.base_prices
        fair_means = [prices - orthogonal_projection(prices_norm, a) for a in self.A.values]
        fairs = [Gaussian(mean, self.covs[i]) for i, mean in enumerate(fair_means)]
        return Gaussian.intersect(fairs)
