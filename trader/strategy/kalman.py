import numpy as np
import pandas as pd
from numpy_ringbuffer import RingBuffer
from statsmodels.tsa.stattools import coint

from trader.strategy.base import Strategy
from trader.util import Gaussian, Log
from trader.util.constants import BTC, EOS, ETH, LTC, NEO, XRP
from trader.util.stats import Ema, HoltEma
from trader.util.types import ex_pair_from_str

# taken from coinmarketcap
# TODO: soon we'll want to be fetching this dynamically
MARKET_CAPS = pd.Series({'BTC': 99e9, 'ETH': 18e9, 'XRP': 14e9, 'EOS': 5e9, 'LTC': 5e9, 'NEO': 7e8})


def add_cap_weighted_basket(P, volumes, name, pairs):
    P_components = P[pairs]
    base_prices = P_components.mean()
    currencies = [repr(ex_pair_from_str(pair).base) for pair in pairs]
    caps = MARKET_CAPS[currencies]
    ratios = 1 / base_prices * caps.values
    P[name] = P_components @ ratios / ratios.sum()
    volumes[name] = volumes[pairs] @ base_prices / P[name].iloc[-1]


def bhattacharyya_multi(a, b):
    """
    Vectorized calculation of Bhattacharyya distance for 1-d Gaussians.
    Formula from https://en.wikipedia.org/wiki/Bhattacharyya_distance.
    """
    return (1 / 4) * (
        np.log((1 / 4) * (a.variance / b.variance + b.variance / a.variance + 2))
        + (a.mean - b.mean) ** 2 / (a.variance + b.variance)
    )


def intersect_with_disagreement(gaussians):
    """
    Intersects 1-d gaussians and scales the intersection variance by a function of disagreement
    betweem the result and the inputs.
    """
    intersection = Gaussian.intersect(gaussians)
    disagreement = pd.DataFrame([bhattacharyya_multi(intersection, g) for g in gaussians])
    return Gaussian(intersection.mean, intersection.variance * (1 + disagreement.pow(2).sum()))


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
        self.moving_volumes = Ema(window_size / 2)
        self.cointegration_period = cointegration_period
        self.maxlag = maxlag
        self.prev_fair = None
        self.sample_counter = 0
        self.coint_f = None

    def tick(self, frame):
        if self.price_history is None:
            self.price_history = RingBuffer(self.window_size, dtype=(np.float64, len(frame.index)))

        self.price_history.append(frame["price"])

        df = pd.DataFrame(self.price_history, columns=frame.index)
        volumes = frame["volume"].copy()
        # Add cap-weighted baskets to the dataset, which should enable better pairwise analysis
        add_cap_weighted_basket(df, volumes, "total_market", frame.index)
        prices = df.iloc[-1]
        # the fair combination step assumes that all estimates are i.i.d. They are not - especially
        # in the case of funds. Is this a problem?
        # Also something to think about - this adds non-exchange-pair columns to df, which may
        # cause type errors if we try to do any manipulation of columns

        moving_prices = self.moving_prices.step(prices)
        moving_volumes = self.moving_volumes.step(volumes)

        if len(self.price_history) < self.window_size or not self.moving_prices.ready:
            return Gaussian(pd.Series([]), [])

        if self.prev_fair is None:
            self.prev_fair = Gaussian(prices, [1e100 for _ in prices])

        if self.coint_f is None:
            self.coint_f = pd.DataFrame(1, index=df.columns, columns=df.columns)

        # The moving average is already trend-compenstated, so we remove trend from the data.
        A = np.vstack([df.index.values, np.ones(len(df.index))]).T
        Q = np.linalg.lstsq(A, df, rcond=None)[0]
        trend = A @ Q
        df -= trend

        # calculate p values for pair cointegration
        if self.sample_counter == 0:
            for i in df.columns:
                for j in df.columns:
                    if str(i) >= str(j):
                        continue
                    p = coint(df[i], df[j], trend="ct", maxlag=self.maxlag, autolag=None)[1]
                    f = 1 + p * p * p * 15625  # .04 -> 2, .05 -> ~3, .1 -> ~16
                    self.coint_f.loc[i, j] = f
                    self.coint_f.loc[j, i] = f
        self.sample_counter = (self.sample_counter - 1) % self.cointegration_period

        diffs = df.diff()[1:]
        var = df.var()
        stddev = np.sqrt(var) + 1e-100
        r = df.corr()
        r2 = r * r
        correlated_slopes = r.mul(stddev, axis=1).div(stddev, axis=0)
        price_ratios = moving_prices[np.newaxis, :] / moving_prices[:, np.newaxis]
        delta = prices - moving_prices
        volume_signals = np.sqrt(moving_volumes * moving_prices)
        volume_f = np.max(volume_signals) / volume_signals
        fair_delta_means = correlated_slopes.mul(delta, axis=0)
        delta_vars = diffs.rolling(self.movement_half_life).sum()[self.movement_half_life :].var()
        correlated_delta_vars = delta_vars[:, np.newaxis] * np.square(price_ratios)
        fair_delta_vars = (
            volume_f
            * self.coint_f
            * ((1 - r2) * delta_vars[np.newaxis, :] + r2 * correlated_delta_vars)
        )
        fair_deltas = [
            Gaussian(fair_delta_means.loc[i], fair_delta_vars.loc[i]) for i in df.columns
        ]
        fair_delta = intersect_with_disagreement(fair_deltas)
        absolute_fair = fair_delta + moving_prices

        step = prices - (self.prev_fair.mean + self.moving_prices.trend)
        fair_step_means = correlated_slopes.mul(step, axis=0)
        step_vars = diffs.var()
        correlated_step_vars = step_vars[:, np.newaxis] * np.square(price_ratios)
        fair_step_vars = (
            volume_f
            * self.coint_f
            * ((1 - r2) * step_vars[np.newaxis, :] + r2 * correlated_step_vars)
        )
        fair_steps = [Gaussian(fair_step_means.loc[i], fair_step_vars.loc[i]) for i in df.columns]
        fair_step = intersect_with_disagreement(fair_steps)
        relative_fair = fair_step + self.prev_fair + self.moving_prices.trend

        fair = absolute_fair & relative_fair
        self.prev_fair = fair
        return fair[frame.index]
