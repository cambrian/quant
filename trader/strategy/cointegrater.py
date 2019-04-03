import pickle

import numpy as np
import pandas as pd

from research.strategy.base import Strategy
from trader.util.linalg import orthogonal_projection
from trader.util.stats import Gaussian


class Cointegrator(Strategy):
    """
    Uses pre-trained cointegration vectors stored in cointegrater.p
    Research team needs to periodically re-train the model. Maybe every month or so.
    """

    def __init__(self):
        coint = pickle.load(open("cointegrater.p", "rb"))
        self.A = coint["cointegrated_vectors"]
        self.historical_mean_prices = coint["mean_prices"]
        self.covs = coint["residual_covariances"]
        self.most_recent_data = coint["most_recent_data"]
        self.prev_prices = None

    def __cointegrated_fairs(self, prices, base_prices):
        prices_norm = prices / base_prices - 1
        fair_means = [
            prices - orthogonal_projection(prices_norm, x) * base_prices for x in self.A.values
        ]
        fairs = [
            Gaussian(mean, self.covs[i] * len(fair_means)) for i, mean in enumerate(fair_means)
        ]
        return Gaussian.intersect(fairs)

    def step(self, frame):
        prices = frame["price"]
        # TODO: be more flexible about input currencies
        # TODO: check that training data was recent enough
        assert np.array_equal(
            prices.index,
            np.array(["BTC_USDT", "XRP_USDT", "ETH_USDT", "LTC_USDT", "NEO_USDT", "EOS_USDT"]),
        )

        if self.prev_prices is None:
            self.prev_prices = prices
            return self.null_estimate(frame)

        step_fairs = self.__cointegrated_fairs(prices, self.prev_prices)
        absolute_fairs = self.__cointegrated_fairs(prices, self.historical_mean_prices)

        return absolute_fairs & step_fairs
