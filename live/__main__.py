# TODO: Add good docstring-style comments.
from trader.constants import BITFINEX, KRAKEN
from trader.exchange import exchanges
from trader.util import manage_threads

import trader.executor as executor
import trader.strategy as strategy

bitfinex_eth_feed = exchanges[BITFINEX].observe('ETHUSD', '1m')
kraken_btc_feed = exchanges[KRAKEN].observe('XBT/USD', 5)
dummy_strategy = strategy.Dummy(bitfinex_eth_feed, kraken_btc_feed)
dummy_executor = executor.Dummy(dummy_strategy.feed)

# Run all threads.
manage_threads(
    *exchanges[BITFINEX].threads,
    *exchanges[KRAKEN].threads,
    dummy_strategy.thread,
    dummy_executor.thread
)
