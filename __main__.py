import trader.strategy as strategy
from trader.exchange import Bitfinex
from trader.executor import Executor
from trader.util.constants import BITFINEX, BTC_USD, ETH_USD
from trader.util.feed import Feed
from trader.util.stats import Gaussian
from trader.util.thread import Beat, ThreadManager

thread_manager = ThreadManager()
bitfinex = Bitfinex(thread_manager)

dummy_strategy = strategy.Dummy()
executor = Executor(thread_manager, {bitfinex: [BTC_USD, ETH_USD]})


def main():
    beat = Beat(60000)
    while beat.loop():
        bitfinex_data = bitfinex.prices([BTC_USD, ETH_USD], "1m")
        dummy_fairs = dummy_strategy.tick(bitfinex_data)
        fairs = Gaussian.intersect([dummy_fairs])
        executor.tick_fairs(fairs)


thread_manager.attach("main", main)
thread_manager.run()
