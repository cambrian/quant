import numpy as np
import pandas as pd
from numpy_ringbuffer import RingBuffer

from strategy import Strategy
from trader.util.stats import Ema, Gaussian


class KalmanFilterStrategy(Strategy):
    """Predicts fairs based on correlated movements between pairs.
    All inputs should be cointegrated."""

    def __init__(self, correlation_window_size, movement_half_life):
        self.moving_prices_history = None
        self.correlation_window_size = correlation_window_size
        self.moving_prices = Ema(movement_half_life)
        self.moving_volumes = Ema(correlation_window_size / 2)
        self.prev_prediction = None

    def step(self, prices, volumes):
        if self.moving_prices_history is None:
            self.moving_prices_history = RingBuffer(
                self.correlation_window_size, dtype=(np.float, len(prices.index))
            )

        if self.prev_prediction is None:
            self.prev_prediction = self.null_estimate(prices)

        self.moving_prices.step(prices)
        self.moving_volumes.step(volumes)

        if not self.moving_prices.ready:
            return self.null_estimate(prices)

        self.moving_prices_history.append(self.moving_prices.value)

        if len(self.moving_prices_history) < self.correlation_window_size:
            return self.null_estimate(prices)

        df = pd.DataFrame(np.array(self.moving_prices_history), columns=prices.index)
        diffs = df.diff().iloc[1:]
        diff = Gaussian(diffs.iloc[-1], diffs.cov())
        # Could also calculate diff from the raw price movements but using smoothed movements
        # for diff seems to improve RoR

        stddevs = df.std()
        corr = df.corr()
        deltas = prices - df.mean()
        predicted_delta_means = corr.mul(deltas, axis=0).mul(stddevs, axis=1).div(stddevs, axis=0)
        volume_signals = np.sqrt(self.moving_volumes.value * self.prev_prediction.mean)
        volume_factor = np.max(volume_signals) / volume_signals
        predicted_delta_variances = (
            np.abs(df.cov().mul(stddevs, axis=1).div(stddevs, axis=0))
            * volume_factor
            / (corr * corr)
        )
        predicted_deltas = Gaussian.intersect(
            [
                Gaussian(predicted_delta_means.loc[i], predicted_delta_variances.loc[i])
                for i in prices.index
            ]
        )

        new_prediction = (self.prev_prediction + diff) & (predicted_deltas + df.mean())
        self.prev_prediction = new_prediction
        return new_prediction
