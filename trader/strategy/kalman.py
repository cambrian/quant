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

    def __init__(self, window_size, cointegration_period, movement_half_life):
        self.price_history = None
        self.window_size = window_size
        self.movement_half_life = movement_half_life
        self.moving_prices = Ema(movement_half_life)
        self.moving_volumes = Ema(window_size / 2)
        self.prev_fair = None
        self.cointegration_period = cointegration_period
        self.sample_counter = 0
        self.coint_f = None

    def tick(self, frame):
        prices = frame["price"]
        volumes = frame["volume"]
        if self.price_history is None:
            self.price_history = RingBuffer(self.window_size, dtype=(np.float, len(prices.index)))

        if self.prev_fair is None:
            self.prev_fair = self.null_estimate(frame)

        if self.coint_f is None:
            self.coint_f = pd.DataFrame(1, index=prices.index, columns=prices.index)

        self.moving_prices.step(prices)
        self.moving_volumes.step(volumes)

        self.price_history.append(prices)

        if len(self.price_history) < self.window_size or not self.moving_prices.ready:
            return self.null_estimate(frame)

        df = pd.DataFrame(self.price_history, columns=prices.index)

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

        var = df.var()
        stddev = np.sqrt(var) + 1e-100
        r = df.corr()
        r2 = r * r
        diffs = df.diff()
        movement_diffs = diffs.rolling(self.movement_half_life).sum()[self.movement_half_life :]
        correlated_slopes = r.mul(stddev, axis=1).div(stddev, axis=0)
        price_ratios = prices[np.newaxis, :] / prices[:, np.newaxis]
        # In theory it's better to substitute self.prev_fair.mean for prices
        # in these calculations, but the difference is marginal and prices is more concise
        volume_signals = np.sqrt(self.moving_volumes.value * prices)
        volume_f = np.max(volume_signals) / volume_signals

        # Calculate fair based on deltas since moving avg
        delta = prices - self.moving_prices.value
        fair_delta_means = correlated_slopes.mul(delta, axis=0)
        correlated_delta_vars = movement_diffs.var()[:, np.newaxis] * np.square(price_ratios)
        fair_delta_vars = (
            volume_f * self.coint_f * ((1 - r2) * var[np.newaxis, :] + r2 * correlated_delta_vars)
        )
        fair_delta = Gaussian.intersect(
            [Gaussian(fair_delta_means.loc[i], fair_delta_vars.loc[i]) for i in prices.index]
        )
        absolute_fair = fair_delta + self.moving_prices.value

        # Calculate fair based on deltas since the last fair estimate
        step = prices - self.prev_fair.mean
        fair_step_means = correlated_slopes.mul(step, axis=0)
        correlated_step_vars = diffs.var()[:, np.newaxis] * np.square(price_ratios)
        fair_step_vars = (
            volume_f * self.coint_f * ((1 - r2) * var[np.newaxis, :] + r2 * correlated_step_vars)
        )
        fair_step = Gaussian.intersect(
            [Gaussian(fair_step_means.loc[i], fair_step_vars.loc[i]) for i in prices.index]
        )
        relative_fair = fair_step + self.prev_fair

        new_fair = absolute_fair & relative_fair
        self.prev_fair = new_fair
        return new_fair
