import warnings

import numpy as np
import pandas as pd
from numpy_ringbuffer import RingBuffer
from statsmodels.tsa.stattools import coint

from trader.strategy.base import Strategy
from trader.util import Gaussian, Log
from trader.util.stats import Ema, Emse, HoltEma


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
        self,
        window_size,
        movement_hl,
        trend_hl,
        mse_hl,
        cointegration_period,
        maxlag,
        warmup_signals,
        warmup_data,
    ):
        self.window_size = window_size
        self.moving_prices = HoltEma(movement_hl, trend_hl, mse_hl)
        self.moving_err_from_prev_fair = Emse(mse_hl)
        self.cointegration_period = cointegration_period
        self.maxlag = maxlag
        self.sample_counter = 0
        self.r = None
        self.r2 = None
        # TODO: do some checks for length/pairs of warmup signals/outputs
        prices = pd.concat(
            [warmup_signals.xs("price", axis=1, level=1), warmup_data.xs("price", axis=1, level=1)],
            axis=1,
            sort=False,
        )
        volumes = pd.concat(
            [
                warmup_signals.xs("volume", axis=1, level=1),
                warmup_data.xs("volume", axis=1, level=1),
            ],
            axis=1,
            sort=False,
        )
        self.price_history = RingBuffer(self.window_size, dtype=(np.float64, len(prices.columns)))
        self.price_history.extend(prices.values)

        for _, p in prices.iloc[-trend_hl * 4 :].iterrows():
            self.moving_prices.step(p)

        self.moving_volumes = Ema(mse_hl, volumes.mean())

        self.moving_variances = Emse(window_size / 2, (prices.diff()[1:] ** 2).mean())

        self.prev_fair = Gaussian(self.moving_prices.value, [1e100 for _ in prices.columns])

        self.coint_f = pd.DataFrame(
            1, index=warmup_signals.columns.unique(0), columns=prices.columns
        )

        if len(self.price_history) < self.window_size or not self.moving_prices.ready:
            Log.warn("Insufficient warmup data. Price model will warm up (slowly) in real time.")
        else:
            Log.info("Price model initialized and warm.")

    # the fair combination step assumes that all signals are i.i.d. They are not (and obviously not in the case
    # of funds). Is this a problem?
    def tick(self, frame, signals):
        prices = pd.concat([signals.xs("price", level=1), frame.xs("price", level=1)], sort=False)
        volumes = pd.concat(
            [signals.xs("volume", level=1), frame.xs("volume", level=1)], sort=False
        )
        input_names = prices.index
        signal_names = signals.index.unique(0)

        self.price_history.append(prices)

        price_history = pd.DataFrame(self.price_history, columns=input_names)

        moving_prices = self.moving_prices.step(prices)
        moving_volumes = self.moving_volumes.step(volumes)

        movement = price_history.iloc[-1] - price_history.iloc[-2]
        self.moving_variances.step(movement)

        if len(self.price_history) < self.window_size or not self.moving_prices.ready:
            return Gaussian(pd.Series([]), [])

        # The moving average is already trend-compenstated, so we remove trend from the data.
        # TODO: remove?
        # price_history = remove_trend(price_history)

        # calculate p values for pair cointegration
        if self.sample_counter == 0:
            for i in signal_names:
                for j in input_names:
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
                        self.coint_f.loc[i, j] = (
                            1 + p * p * p * 15625
                        )  # .04 -> 2, .05 -> ~3, .1 -> 15.625
            self.r = price_history.corr().loc[signal_names]
            self.r2 = self.r ** 2

        self.sample_counter = (self.sample_counter - 1) % self.cointegration_period

        stddev = self.moving_variances.stderr
        correlated_slopes = self.r.mul(stddev, axis=1).div(stddev[signal_names], axis=0)
        log_volume = np.log1p(moving_volumes)
        # ideally use mkt cap instead of volume?
        volume_f = pd.DataFrame(
            log_volume[np.newaxis, :] - log_volume[signal_names][:, np.newaxis],
            index=signal_names,
            columns=input_names,
        )
        volume_f = volume_f * (volume_f > 0) + 1

        delta = signals.xs("price", level=1) - moving_prices[signal_names]
        fair_delta_means = correlated_slopes.mul(delta, axis=0)
        delta_vars = self.moving_prices.mse
        correlated_delta_vars = np.square(correlated_slopes).mul(delta_vars[signal_names], axis=0)
        fair_delta_vars = (correlated_delta_vars + (1 - self.r2) * self.coint_f * delta_vars).mul(
            volume_f, axis=0
        )
        fair_deltas = [
            Gaussian(fair_delta_means.loc[i], fair_delta_vars.loc[i]) for i in signal_names
        ]
        fair_delta = intersect_with_disagreement(fair_deltas)
        absolute_fair = fair_delta + moving_prices

        step = prices - (self.prev_fair.mean + self.moving_prices.trend)
        step_vars = self.moving_err_from_prev_fair.step(step)
        fair_step_means = correlated_slopes.mul(step[signal_names], axis=0)
        correlated_step_vars = np.square(correlated_slopes).mul(step_vars[signal_names], axis=0)
        fair_step_vars = (correlated_step_vars + (1 - self.r2) * self.coint_f * step_vars).mul(
            volume_f, axis=0
        )
        fair_steps = [Gaussian(fair_step_means.loc[i], fair_step_vars.loc[i]) for i in signal_names]
        fair_step = intersect_with_disagreement(fair_steps)
        relative_fair = fair_step + self.prev_fair + self.moving_prices.trend

        fair = intersect_with_disagreement([absolute_fair, relative_fair])
        self.prev_fair = fair
        return fair[frame.index.unique(0)]
