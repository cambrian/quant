import numpy as np
import pandas as pd

from trader.util.constants import BCH, BTC, EOS, ETH, LTC, NEO, XRP
from trader.util.stats import Ema
from trader.util.types import ExchangePair, TradingPair

# TODO: fetch this dynamically
CIRCULATING_SUPPLY = pd.Series(
    {BTC: 18e6, ETH: 106e6, XRP: 42e9, BCH: 18e6, EOS: 913e6, LTC: 62e6, NEO: 65e6}
)

# TODO:
# think about how to do this. what if a quote_usd pair does not exist on a particular exchange?
def convert_quotes_to_usd(frame):
    frame = frame.copy()
    frame["volume"] *= frame["price"]
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
    currencies = {pair.base for pair in frame.index}
    aggregates = pd.DataFrame(index=currencies, columns=frame.columns)
    for c in currencies:
        components = frame.filter(regex="-" + repr(c) + "-.*", axis=0)
        moving_volumes_c = moving_volumes.filter(regex="-" + repr(c) + "-.*") + 1e-10
        volume = components["volume"].sum()
        price = components["price"] @ moving_volumes_c / moving_volumes_c.sum()
        aggregates.loc[c] = (price, volume)
    return aggregates


def add_baskets_mut(baskets, aggregates):
    """
    Compute a cap-weighted basket of currencies. Input should have aggregate quotes.
    """
    for name, currencies in baskets.items():
        components = aggregates.loc[currencies]
        # scale down to avoid numerical instability
        price = components["price"] @ CIRCULATING_SUPPLY[currencies] / 1e9
        volume = components["volume"].sum()
        aggregates.loc[name] = (price, volume)


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
        moving_volumes = self.__moving_volumes.step(frame["volume"])
        aggregates = aggregate_currency_quotes(moving_volumes, frame)
        add_baskets_mut(self.__baskets, aggregates)
        return aggregates.astype(np.float64)
