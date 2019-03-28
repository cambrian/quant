import trader.executor as executor
import trader.strategy as strategy
from trader.exchange import Exchanges
from trader.util.constants import BITFINEX, BTC_USD
from trader.util.stats import Gaussian
from trader.util.thread import Beat, ThreadManager

bitfinex = Exchanges.get(BITFINEX)
dummy_strategy = strategy.Dummy()
dummy_executor = executor.Dummy()


def main():
    beat = Beat(60000)
    while beat.loop():
        bitfinex_data = bitfinex.prices([BTC_USD], "1m")
        dummy_fairs = dummy_strategy.tick(bitfinex_data)
        fairs = Gaussian.intersect([dummy_fairs])
        dummy_executor.tick_fairs(fairs)


bitfinex_btc_usd_feed = bitfinex.book(BTC_USD)
executor_book_runner = bitfinex_btc_usd_feed.subscribe(dummy_executor.tick_book)

thread_manager = ThreadManager()
thread_manager.attach("main", main)
thread_manager.attach("bitfinex-btc-usd-feed", bitfinex_btc_usd_feed.run)
thread_manager.attach("executor-book-runner", executor_book_runner)
thread_manager.run()
