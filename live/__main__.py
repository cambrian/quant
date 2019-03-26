from trader.exchange import Exchanges
from trader.util.constants import BITFINEX
from trader.util.thread import ThreadManager

import trader.executor as executor
import trader.strategy as strategy
thread_manager = ThreadManager()

# Initialize exchange singletons. Note that Bitfinex (and other exchanges in the future) require
# you to put API keys in specific environment variables.
bitfinex = Exchanges.get(BITFINEX)

# Declare a new feed from Bitfinex price data (this only wires it up).
bitfinex_btc_usd_1m = bitfinex.feed(thread_manager, 'BTCUSD', '1m')

# Initialize and wire up our Dummy strategy. Strategies require particular feeds to be available to
# them, and this is enforced on startup when things are being wired together.
dummy_strategy = strategy.Dummy(thread_manager, {
    (BITFINEX, 'BTCUSD', '1m'): bitfinex_btc_usd_1m
})

# Initialize and wire up our Dummy executor. In a similar vein, executors require particular
# strategies to be available to them; this is also checked on startup.
dummy_executor = executor.Dummy(thread_manager, {
    strategy.Dummy: dummy_strategy.feed
})

# Run components (forever).
thread_manager.run()
