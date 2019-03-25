from trader.exchange import Exchanges
from trader.util.constants import BITFINEX, KRAKEN
from trader.util.thread import ThreadManager

import trader.executor as executor
import trader.strategy as strategy

# Get singleton exchange instances.
feed_thread_manager = ThreadManager()
bitfinex = Exchanges.get(BITFINEX)

# Declare a new feed from Bitfinex price data (this only wires it up).
bitfinex_btc_usd_1m = bitfinex.observe(feed_thread_manager, 'BTCUSD', '1m')

# Initialize and wire up our Dummy strategy.
dummy_strategy = strategy.Dummy(feed_thread_manager, {
    (BITFINEX, 'BTCUSD', '1m'): bitfinex_btc_usd_1m
})

# Initialize and wire up our Dummy executor.
dummy_executor = executor.Dummy(feed_thread_manager, {
    strategy.Dummy: dummy_strategy.feed
})

# Run feed processors.
feed_thread_manager.run()
