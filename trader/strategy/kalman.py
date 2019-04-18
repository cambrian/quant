import numpy as np
import pandas as pd
from numpy_ringbuffer import RingBuffer
from statsmodels.tsa.stattools import coint

from trader.strategy.base import Strategy
from trader.util.stats import Ema, Gaussian


class Kalman(Strategy):
    """
    Models fairs based on correlated movements between pairs. Weights predictions by volume and
    likelihood of cointegration.
    """

    def __init__(self, correlation_window_size, movement_half_life, cointegration_freq=4):
        self.moving_prices_history = None
        self.correlation_window_size = correlation_window_size
        self.moving_prices = Ema(movement_half_life)
        self.moving_volumes = Ema(correlation_window_size / 2)
        self.prev_fair = None
        self.cointegration_period = correlation_window_size // cointegration_freq
        self.sample_counter = 0
        self.coint_f = None

    def tick(self, frame):
        prices = frame["price"]
        volumes = frame["volume"]
        if self.moving_prices_history is None:
            self.moving_prices_history = RingBuffer(
                self.correlation_window_size, dtype=(np.float, len(prices.index))
            )

        if self.prev_fair is None:
            self.prev_fair = self.null_estimate(frame)

        if self.coint_f is None:
            self.coint_f = pd.DataFrame(1, index=prices.index, columns=prices.index)

        self.moving_prices.step(prices)
        self.moving_volumes.step(volumes)

        if not self.moving_prices.ready:
            return self.null_estimate(frame)

        self.moving_prices_history.append(self.moving_prices.value)

        if len(self.moving_prices_history) < self.correlation_window_size:
            return self.null_estimate(frame)

        df = pd.DataFrame(self.moving_prices_history, columns=prices.index)

        # calculate p values for pair cointegration
        if self.sample_counter == 0:
            deltas = df - df.mean()
            for i in prices.index:
                for j in prices.index:
                    if i >= j:
                        continue
                    p = coint(deltas[i], deltas[j], trend="nc", maxlag=0, autolag=None)[1]
                    f = max(1, p * 40)
                    self.coint_f.loc[i, j] = f
                    self.coint_f.loc[j, i] = f
        self.sample_counter = (self.sample_counter - 1) % self.cointegration_period

        diffs = df.diff()
        step = Gaussian(diffs.iloc[-1], diffs.cov())
        relative_fair = self.prev_fair + step

        var = df.var()
        stddev = np.sqrt(var) + 1e-100
        r = df.corr()
        r2 = r * r
        delta = prices - self.moving_prices.value
        # In theory it's better to substitute self.prev_fair.mean for prices
        # in these calculations, but the difference is marginal and prices is more concise
        volume_signals = np.sqrt(self.moving_volumes.value * prices)
        volume_f = np.max(volume_signals) / volume_signals
        fair_delta_means = r.mul(delta, axis=0).mul(stddev, axis=1).div(stddev, axis=0)
        correlated_vars = (diffs.var() / prices.pow(2))[:, np.newaxis] * prices.pow(2)[
            np.newaxis, :
        ]
        fair_delta_vars = (
            volume_f * self.coint_f * ((1 - r2) * var[np.newaxis, :] + r2 * correlated_vars)
        )
        fair_deltas = Gaussian.intersect(
            [Gaussian(fair_delta_means.loc[i], fair_delta_vars.loc[i]) for i in prices.index]
        )
        absolute_fair = fair_deltas + self.moving_prices.value

        new_fair = absolute_fair & relative_fair
        self.prev_fair = new_fair
        return new_fair
