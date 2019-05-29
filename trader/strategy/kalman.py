import warnings

import numpy as np
import pandas as pd
from numpy_ringbuffer import RingBuffer
from statsmodels.tsa.stattools import coint

from trader.strategy.base import Strategy
from trader.util import Gaussian
from trader.util.stats import Ema, HoltEma
from trader.util.types import ExchangePair


def bhattacharyya_multi(a, b):
    """
    Vectorized calculation of Bhattacharyya distance for 1-d Gaussians.
    Formula from https://en.wikipedia.org/wiki/Bhattacharyya_distance
    """
    return (1 / 4) * (
        np.log((1 / 4) * (a.variance / b.variance + b.variance / a.variance + 2))
        + (a.mean - b.mean) ** 2 / (a.variance + b.variance)
    )


def intersect_with_disagreement(gaussians):
    intersection = Gaussian.intersect(gaussians)
    disagreement = pd.DataFrame([bhattacharyya_multi(intersection, g) for g in gaussians])
    return Gaussian(intersection.mean, intersection.variance * (1 + disagreement.pow(2).sum()))


def remove_trend(df):
    """Remove linear trend from the input data by subtracting the OLS."""
    A = np.vstack([df.index.values, np.ones(len(df.index))]).T
    Q = np.linalg.lstsq(A, df, rcond=None)[0]
    trend = A @ Q
    return df - trend


class Kalman(Strategy):
    """
    Models fairs based on correlated movements between pairs. Weights predictions by volume and
    likelihood of cointegration.
    """

    def __init__(
        self, window_size, movement_half_life, trend_half_life, cointegration_period, maxlag
    ):
        self.price_history = None
        self.window_size = window_size
        self.movement_half_life = movement_half_life
        self.moving_prices = HoltEma(movement_half_life, trend_half_life)
        self.moving_signal_volumes = Ema(window_size / 2)
        self.cointegration_period = cointegration_period
        self.maxlag = maxlag
        self.prev_fair = None
        self.sample_counter = 0
        self.coint_f = None

    # the fair combination step assumes that all signals are i.i.d. They are not (and obviously not in the case
    # of funds). Is this a problem?
    def tick(self, frame, signals):
        inputs = pd.concat([frame, signals])
        if self.price_history is None:
            self.price_history = RingBuffer(self.window_size, dtype=(np.float64, len(inputs.index)))

        self.price_history.append(inputs["price"])

        price_history = pd.DataFrame(self.price_history, columns=inputs.index)

        moving_prices = self.moving_prices.step(inputs["price"])
        moving_signal_volumes = self.moving_signal_volumes.step(signals["volume"])

        if len(self.price_history) < self.window_size or not self.moving_prices.ready:
            return Gaussian(pd.Series([]), [])

        if self.prev_fair is None:
            self.prev_fair = Gaussian(moving_prices, [1e100 for _ in inputs.index])

        if self.coint_f is None:
            self.coint_f = pd.DataFrame(1, index=signals.index, columns=inputs.index)

        # The moving average is already trend-compenstated, so we remove trend from the data.
        price_history = remove_trend(price_history)

        # calculate p values for pair cointegration
        if self.sample_counter == 0:
            for i in signals.index:
                for j in inputs.index:
                    # ignore collinearity warning
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore")
                        p = coint(
                            price_history[i],
                            price_history[j],
                            trend="ct",
                            maxlag=self.maxlag,
                            autolag=None,
                        )[1]
                        # .04 -> 2, .05 -> ~3, .1 -> 15.625
                        self.coint_f.loc[i, j] = 1 + p * p * p * 15625
        self.sample_counter = (self.sample_counter - 1) % self.cointegration_period

        diffs = price_history.diff()[1:]
        var = price_history.var()
        stddev = np.sqrt(var) + 1e-100
        r = price_history.corr().loc[signals.index]
        r2 = r * r
        correlated_slopes = r.mul(stddev, axis=1).div(stddev[signals.index], axis=0)
        sqrt_volume = np.sqrt(moving_signal_volumes)
        volume_f = np.max(sqrt_volume) / sqrt_volume
        f = self.coint_f.mul(volume_f, axis=0)

        delta = signals["price"] - moving_prices[signals.index]
        fair_delta_means = correlated_slopes.mul(delta, axis=0)
        delta_vars = diffs.rolling(self.movement_half_life).sum()[self.movement_half_life :].var()
        correlated_delta_vars = np.square(correlated_slopes).mul(delta_vars[signals.index], axis=0)
        fair_delta_vars = f * correlated_delta_vars + (1 - r2) * delta_vars
        fair_deltas = [
            Gaussian(fair_delta_means.loc[i], fair_delta_vars.loc[i]) for i in signals.index
        ]
        fair_delta = intersect_with_disagreement(fair_deltas)
        absolute_fair = fair_delta + moving_prices

        step = signals["price"] - (self.prev_fair.mean + self.moving_prices.trend)[signals.index]
        fair_step_means = correlated_slopes.mul(step, axis=0)
        step_vars = diffs.var()
        correlated_step_vars = np.square(correlated_slopes).mul(step_vars[signals.index], axis=0)
        fair_step_vars = f * correlated_step_vars + (1 - r2) * step_vars
        fair_steps = [
            Gaussian(fair_step_means.loc[i], fair_step_vars.loc[i]) for i in signals.index
        ]
        fair_step = intersect_with_disagreement(fair_steps)
        relative_fair = fair_step + self.prev_fair + self.moving_prices.trend

        fair = intersect_with_disagreement([absolute_fair, relative_fair])
        self.prev_fair = fair
        return fair[frame.index]
