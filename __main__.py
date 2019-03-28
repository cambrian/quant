import trader.executor as executor
import trader.strategy as strategy
from trader.exchange import Exchanges
from trader.util.constants import BITFINEX, BTC_USD
from trader.util.feed import Feed
from trader.util.stats import Gaussian
from trader.util.thread import Beat, ThreadManager

bitfinex = Exchanges.get(BITFINEX)
dummy_strategy = strategy.Dummy()
dummy_executor = executor.Dummy()


def fairs_generator():
    beat = Beat(60000)
    while beat.loop():
        bitfinex_data = bitfinex.prices([BTC_USD], "1m")
        dummy_fairs = dummy_strategy.tick(bitfinex_data)
        yield Gaussian.intersect([dummy_fairs])


fairs_feed = Feed(fairs_generator())
executor_fairs_runner = fairs_feed.subscribe(dummy_executor.tick_fairs)

# TODO: Have this also update `.prices`.
bitfinex_btc_usd_feed = bitfinex.book(BTC_USD)
executor_book_runner = bitfinex_btc_usd_feed.subscribe(dummy_executor.tick_book)

thread_manager = ThreadManager()
thread_manager.attach("fairs-feed", fairs_feed.run)
thread_manager.attach("executor-fairs-runner", executor_fairs_runner)
thread_manager.attach("bitfinex-btc-usd-feed", bitfinex_btc_usd_feed.run)
thread_manager.attach("executor-book-runner", executor_book_runner)
thread_manager.attach("bitfinex-balance-watcher", bitfinex.track_balances)
thread_manager.run()
