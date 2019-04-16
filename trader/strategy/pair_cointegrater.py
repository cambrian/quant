import numpy as np
import pandas as pd
from numpy_ringbuffer import RingBuffer
from statsmodels.tsa.stattools import coint

from trader.strategy.base import Strategy
from trader.util.linalg import hyperplane_projection, orthogonal_projection
from trader.util.stats import Ema, Gaussian


class PairCointegrator(Strategy):
    def __init__(self, window_size, cointegration_frequency=4):
        self.window_size = window_size
        self.cointegration_period = window_size // cointegration_frequency
        self.sample_counter = 0
        self.price_history = None

    def tick(self, frame):
        prices = frame["price"]

        if self.price_history is None:
            self.price_history = RingBuffer(self.window_size, dtype=(np.float64, len(prices.index)))

        self.price_history.append(prices)

        if len(self.price_history) < self.window_size:
            return self.null_estimate(prices)

        if self.sample_counter == 0:
            df = pd.DataFrame(self.price_history, columns=prices.index)
            self.mean = df.mean()
            deltas = df / self.mean - 1
            stddev = deltas.std() + 1e-10
            self.regression_slope = deltas.corr().mul(stddev, axis=1).div(stddev, axis=0)

            coint_p = pd.DataFrame(0, index=prices.index, columns=prices.index)
            prediction_covs = {}
            for pair_i in prices.index:
                for pair_j in prices.index:
                    if pair_i >= pair_j:
                        continue
                    p = coint(df[pair_i], df[pair_j], maxlag=0, autolag=None)[1]
                    coint_p.loc[pair_i, pair_j] = p
                    coint_p.loc[pair_j, pair_i] = p
                    deltas_ij = deltas[[pair_i, pair_j]]
                    regression_vector = [self.regression_slope.loc[pair_i][pair_j], -1]
                    cov_pred = orthogonal_projection(deltas_ij, regression_vector).cov()
                    # regularize prediction covariance by using the raw price covariance shape with the
                    # prediction covariance slope
                    cov_sam = deltas_ij.cov()
                    w_pred, v_pred = np.linalg.eigh(cov_pred)
                    w_sam, v_sam = np.linalg.eigh(cov_sam)
                    eigenvalue_ratio_sam = w_sam[1] / w_sam[0]
                    w_reg = w_pred[1] * np.array([eigenvalue_ratio_sam, 1])
                    cov_reg = v_pred @ np.diag(w_reg) @ v_pred.T
                    cov_reg = pd.DataFrame(
                        cov_reg, index=deltas_ij.columns, columns=deltas_ij.columns
                    )
                    prediction_covs[pair_i, pair_j] = cov_reg
                    prediction_covs[pair_j, pair_i] = cov_reg[::-1].T[::-1]
            # discount predictions for p values > .03
            self.coint_f = (coint_p * coint_p * 900).clip(1)
            self.prediction_covs = prediction_covs

        self.sample_counter -= 1
        self.sample_counter %= self.cointegration_period

        if self.coint_f is None:
            return self.null_estimate(prices)

        fairs = []
        delta = prices / self.mean - 1
        for pair_i in prices.index:
            for pair_j in prices.index:
                if pair_i >= pair_j:
                    continue
                regression_vector = [self.regression_slope.loc[pair_i][pair_j], -1]
                fair_delta_mean = hyperplane_projection(delta[[pair_i, pair_j]], regression_vector)
                fair_cov = self.prediction_covs[pair_i, pair_j] * self.coint_f.loc[pair_i, pair_j]
                fair = Gaussian(fair_delta_mean, fair_cov)
                fairs.append(fair)
        fair = (Gaussian.intersect(fairs) + 1) * self.mean
        return fair
