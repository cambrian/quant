import trader.executor as executor
import trader.strategy as strategy
from trader.exchange import Exchanges
from trader.util.constants import BITFINEX, BTC_USD
from trader.util.feed import Feed
from trader.util.stats import Gaussian
from trader.util.thread import Beat, ThreadManager

thread_manager = ThreadManager()
Exchanges.set_thread_manager(thread_manager)

dummy_strategy = strategy.Dummy()
dummy_executor = executor.Dummy(thread_manager, {BITFINEX: [BTC_USD]})


def main():
    beat = Beat(60000)
    while beat.loop():
        bitfinex = Exchanges.get(BITFINEX)
        bitfinex_data = bitfinex.prices([BTC_USD], "1m")
        dummy_fairs = dummy_strategy.tick(bitfinex_data)
        fairs = Gaussian.intersect([dummy_fairs])
        dummy_executor.tick_fairs(fairs)


thread_manager.attach("main", main)
thread_manager.run()
