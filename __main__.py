import pandas as pd

import trader.strategy as strategy
from trader.exchange import Bitfinex, DummyExchange
from trader.executor import Executor
from trader.util.constants import BITFINEX, BTC_USD, BTC_USDT, ETH_USD
from trader.util.feed import Feed
from trader.util.stats import Gaussian
from trader.util.thread import Beat, ThreadManager

thread_manager = ThreadManager()
bitfinex = Bitfinex(thread_manager)
# If you don't have research/data/1min.h5, download 1min from S3 and run hd5.ipynb
# data_min = pd.read_hdf("research/data/1min.h5")
# dummy_exchange = DummyExchange(thread_manager, data_min, {})

dummy_strategy = strategy.Dummy()
executor = Executor(thread_manager, {bitfinex: [BTC_USD, ETH_USD]})


def main():
    beat = Beat(60000)
    while beat.loop():
        bitfinex_data = bitfinex.prices([BTC_USD, ETH_USD], "1m")
        dummy_fairs = dummy_strategy.tick(bitfinex_data)
        fairs = Gaussian.intersect([dummy_fairs])
        executor.tick_fairs(fairs)
        # dummy_Data = dummy_exchange.prices([BTC_USDT], "1m")
        # dummy_exchange.step_time()


# book_feed = dummy_exchange.book(BTC_USDT)
thread_manager.attach("main", main)
thread_manager.run()
