from trader.exchange import Exchanges
from trader.util.constants import BITFINEX
from trader.util.thread import ThreadManager

import trader.executor as executor
import trader.strategy as strategy

# Get a thread manager and singletons.
thread_manager = ThreadManager()
bitfinex = Exchanges.get(BITFINEX)

# Declare a new feed from Bitfinex price data (this only wires it up).
bitfinex_btc_usd_1m = bitfinex.feed(thread_manager, 'BTCUSD', '1m')

# Initialize and wire up our Dummy strategy.
dummy_strategy = strategy.Dummy(thread_manager, {
    (BITFINEX, 'BTCUSD', '1m'): bitfinex_btc_usd_1m
})

# Initialize and wire up our Dummy executor.
dummy_executor = executor.Dummy(thread_manager, {
    strategy.Dummy: dummy_strategy.feed
})

# Run feed processors.
thread_manager.run()
