import numpy as np

from trader.util import Log
from trader.util.stats import HoltEma, TrendEstimator


class ExecutionStrategy:
    def __init__(
        self,
        size,
        micro_trend_hl,
        micro_accel_hl,
        trend_hl,
        accel_hl,
        edge_trend_hl,
        edge_accel_hl,
        warmup_data,
    ):
        self.size = size

        warmup_prices = warmup_data.xs("price", axis=1, level=1)
        latest_prices = warmup_prices.iloc[-1]

        self.micro_trend_estimator = TrendEstimator(
            HoltEma(micro_trend_hl, micro_accel_hl), latest_prices
        )
        self.trend_estimator = TrendEstimator(HoltEma(trend_hl, accel_hl), latest_prices)
        for _, prices in warmup_prices.iloc[-4 * accel_hl :].iterrows():
            self.micro_trend_estimator.step(prices)
            self.trend_estimator.step(prices)
        self.edge_trend_estimator = TrendEstimator(HoltEma(edge_trend_hl, edge_accel_hl))

        if not self.trend_estimator.ready:
            Log.warn(
                "Execution strategy initialized but had insufficient warmup data. Will \
                warm up slowly in real time."
            )
        else:
            Log.info("Execution strategy initialized and warm.")

    def tick(self, positions, bids, asks, fairs, fees):
        """Takes fair as Gaussian, positions in base currency.
        Returns orders in base currency (negative size indicates sell).

        Since our fair estimate may have skewed uncertainty, it may be the case that
        a price change for one trading pair causes us to desire positions in other
        pairs. Therefore get_orders needs to consider the entire set of fairs and
        bid/asks at once.

        TODO: generalize to multiple quotes
        TODO: use books instead of just the best bid/ask price
        """
        mids = (bids + asks) / 2  # Use mid price for target position value calculations.
        prices = (fairs.mean >= mids) * asks + (fairs.mean < mids) * bids

        micro_trend = self.micro_trend_estimator.step(mids)
        trend = self.trend_estimator.step(mids)
        edge_trend = self.edge_trend_estimator.step(fairs.mean / mids - 1)

        z_edge = (fairs.mean - prices) / fairs.stddev
        pct_edge = fairs.mean / prices - 1
        net_pct_edge = np.sign(pct_edge) * np.maximum(0, np.abs(pct_edge) - 2 * fees)
        target_position_values = (
            np.sign(pct_edge) * np.sqrt(z_edge * net_pct_edge * 100) * self.size
        )
        pair_positions = positions[[(ep.exchange_id, ep.base) for ep in mids.index]].set_axis(
            mids.index, inplace=False
        )
        proposed_orders = target_position_values / fairs.mean - pair_positions
        profitable = np.sign(proposed_orders) * pct_edge > 2 * fees
        profitable_orders = proposed_orders * profitable

        unprofitable_position = np.sign(pair_positions) * pct_edge < 0
        position_closing_orders = -pair_positions * (profitable_orders == 0) * unprofitable_position

        trending_correctly = (trend * np.sign(pct_edge) > 0) & micro_trend * np.sign(pct_edge) > 0
        reverting = edge_trend * np.sign(pct_edge) < 0

        return (profitable_orders + position_closing_orders) * trending_correctly * reverting
