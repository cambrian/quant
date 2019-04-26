import numpy as np
import pandas as pd
from numpy_ringbuffer import RingBuffer
from statsmodels.tsa.stattools import coint

from trader.strategy.base import Strategy
from trader.util.constants import BTC, EOS, ETH, LTC, NEO, XRP
from trader.util.log import Log
from trader.util.stats import Ema, Gaussian

# taken from coinmarketcap
# TODO: soon we'll want to be fetching this dynamically
MARKET_CAPS = pd.Series({BTC: 99e9, ETH: 18e9, XRP: 14e9, EOS: 5e9, LTC: 5e9, NEO: 7e8})


def add_cap_weighted_basket(P, volumes, name, pairs):
    P_components = P[pairs]
    base_prices = P_components.mean()
    currencies = [pair.base for pair in pairs]
    caps = MARKET_CAPS[currencies]
    ratios = 1 / base_prices * caps.values
    P[name] = P_components @ ratios / ratios.sum()
    volumes[name] = volumes[pairs] @ base_prices / P[name].iloc[-1]


class Kalman(Strategy):
    """
    Models fairs based on correlated movements between pairs. Weights predictions by volume and
    likelihood of cointegration.
    """

    def __init__(self, window_size, movement_half_life, cointegration_period, maxlag):
        self.price_history = None
        self.window_size = window_size
        self.movement_half_life = movement_half_life
        self.moving_prices = Ema(movement_half_life)
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

        self.moving_prices.step(prices)
        self.moving_volumes.step(volumes)

        if len(self.price_history) < self.window_size or not self.moving_prices.ready:
            return self.null_estimate(frame)

        if self.prev_fair is None:
            self.prev_fair = self.null_estimate(frame)

        if self.coint_f is None:
            self.coint_f = pd.DataFrame(1, index=df.columns, columns=df.columns)

        # calculate p values for pair cointegration
        if self.sample_counter == 0:
            deltas = df - df.mean()
            for i in df.columns:
                for j in df.columns:
                    if i >= j:
                        continue
                    p = coint(deltas[i], deltas[j], trend="nc", maxlag=self.maxlag, autolag=None)[1]
                    f = max(1, p * p * 2500)
                    self.coint_f.loc[i, j] = f
                    self.coint_f.loc[j, i] = f
        self.sample_counter = (self.sample_counter - 1) % self.cointegration_period

        diffs = df.diff()
        var = df.var()
        stddev = np.sqrt(var) + 1e-100
        r = df.corr()
        r2 = r * r
        correlated_slopes = r.mul(stddev, axis=1).div(stddev, axis=0)
        price_ratios = prices[np.newaxis, :] / prices[:, np.newaxis]
        delta = prices - self.moving_prices.value
        # In theory it's better to substitute self.prev_fair.mean for prices
        # in these calculations, but the difference is marginal and prices is more concise
        volume_signals = np.sqrt(self.moving_volumes.value * prices)
        volume_f = np.max(volume_signals) / volume_signals
        fair_delta_means = correlated_slopes.mul(delta, axis=0)
        delta_vars = diffs.rolling(self.movement_half_life).sum()[self.movement_half_life :]
        correlated_delta_vars = delta_vars[:, np.newaxis] * np.square(price_ratios)
        fair_delta_vars = (
            volume_f
            * self.coint_f
            * ((1 - r2) * delta_vars[np.newaxis, :] + r2 * correlated_delta_vars)
        )
        fair_delta = Gaussian.intersect(
            [Gaussian(fair_delta_means.loc[i], fair_delta_vars.loc[i]) for i in df.columns]
        )
        absolute_fair = fair_delta + self.moving_prices.value

        step = prices - self.prev_fair.mean
        fair_step_means = correlated_slopes.mul(step, axis=0)
        step_vars = diffs.var()
        correlated_step_vars = step_vars[:, np.newaxis] * np.square(price_ratios)
        fair_step_vars = (
            volume_f
            * self.coint_f
            * ((1 - r2) * step_vars[np.newaxis, :] + r2 * correlated_step_vars)
        )
        fair_step = Gaussian.intersect(
            [Gaussian(fair_step_means.loc[i], fair_step_vars.loc[i]) for i in df.columns]
        )
        relative_fair = fair_step + self.prev_fair

        fair = absolute_fair & relative_fair
        self.prev_fair = fair
        return fair[frame.index]
