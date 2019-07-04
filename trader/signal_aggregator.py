import numpy as np
import pandas as pd

from trader.util.constants import BCH, BSV, BTC, EOS, ETH, LTC, NEO, XRP
from trader.util.stats import Ema

# TODO: fetch this dynamically
CIRCULATING_SUPPLY = pd.Series(
    {BTC: 18e6, ETH: 106e6, XRP: 42e9, BCH: 18e6, EOS: 913e6, LTC: 62e6, NEO: 65e6, BSV: 18e6}
)

# TODO: actually convert quotes, not just volume
# think about how to do this. what if a quote_usd pair does not exist on a :particular exchange?
def convert_quotes_to_usd(frame):
    frame = frame.copy()
    # .values call necessary because assigning to indexslices is buggy
    # see https://github.com/pandas-dev/pandas/issues/10440
    frame.loc[pd.IndexSlice[:, "volume"]] = (
        frame.xs("volume", level=1) * frame.xs("price", level=1)
    ).values
    return frame


def aggregate_currency_quotes(moving_volumes, frame):
    """
    Aggregate quotes for the same base currency across all exchanges and pairs. Quotes should
    already be in USD.

    Returns aggregate quotes.

    Note: this may cause unwanted fluctuation in the aggregate price if quotes disagree - and
    trading volume moves back and forth between them. To combat this we weight quotes by a slow
    moving average of trading volume, but is there a better solution?
    """
    currencies = {pair.base for pair in frame.index.unique(level=0)}
    index = pd.MultiIndex.from_product([currencies, frame.index.unique(level=1)])
    aggregates = pd.Series(index=index)
    for c in currencies:
        components = frame.filter(regex="-" + str(c) + "-.*", axis=0)
        moving_volumes_c = moving_volumes.filter(regex="-" + str(c) + "-.*") + 1e-10
        volume = components.xs("volume", level=1).sum()
        price = components.xs("price", level=1) @ moving_volumes_c / moving_volumes_c.sum()
        aggregates.loc[pd.IndexSlice[c, :]] = (price, volume)

    return aggregates


def compute_baskets(basket_specs, aggregates):
    """
    Compute a cap-weighted basket of currencies. Input should have aggregate quotes.
    """
    index = pd.MultiIndex.from_product([basket_specs, aggregates.index.unique(level=1)])
    baskets = pd.Series(index=index)
    for name, currencies in basket_specs.items():
        components = aggregates.loc[pd.IndexSlice[currencies, :]]
        # scale down to avoid numerical instability
        price = components.xs("price", level=1) @ CIRCULATING_SUPPLY[currencies] / 1e9
        volume = components.xs("volume", level=1).sum()
        baskets.loc[pd.IndexSlice[name, :]] = (price, volume)
    return baskets


class SignalAggregator:
    """
    Adds cap-weighted baskets to frame.
    TODO: also convert non-USD quotes to USD, add aggregated currency prices
    """

    def __init__(self, volume_half_life, baskets):
        self.__moving_volumes = Ema(volume_half_life)
        self.__baskets = baskets

    def step(self, frame):
        frame = convert_quotes_to_usd(frame)
        moving_volumes = self.__moving_volumes.step(frame.xs("volume", level=1))
        aggregates = aggregate_currency_quotes(moving_volumes, frame)
        baskets = compute_baskets(self.__baskets, aggregates)
        signals = pd.concat([aggregates, baskets]).astype(np.float64)
        return signals
