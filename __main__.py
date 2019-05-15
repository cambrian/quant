import pandas as pd

import trader.strategy as strategy
from trader.exchange import Bitfinex, DummyExchange
from trader.executor import Executor
from trader.metrics import Metrics
from trader.util import Feed, Gaussian, Log
from trader.util.constants import (BTC_USD, BTC_USDT, ETH_USD, ETH_USDT,
                                   LTC_USDT, XRP_USDT)
from trader.util.thread import Beat, ThreadManager
from trader.util.types import Direction, Order

thread_manager = ThreadManager()
bitfinex = Bitfinex(thread_manager)
data_min = pd.read_hdf("research/data/1min.h5")
dummy_exchange = DummyExchange(thread_manager, data_min, {})

# dummy_strategy = strategy.Dummy()
# cointegrator_strategy = strategy.Cointegrator(
#     train_size=1200, validation_size=600, cointegration_period=64
# )
window_size = 7500
kalman_strategy = strategy.Kalman(
    window_size=window_size,
    movement_half_life=90,
    trend_half_life=3000,
    cointegration_period=60,
    maxlag=120,
)
executor = Executor(thread_manager, {bitfinex: [BTC_USD, ETH_USD]}, size=10, min_edge=0.0005)
# executor = Executor(thread_manager, {dummy_exchange: [BTC_USDT, ETH_USDT]}, size=100, min_edge=0)
# metrics = Metrics(thread_manager, {bitfinex})


def main():
    beat = Beat(60000)
    bitfinex.warm_up([BTC_USD, ETH_USD], window_size, kalman_strategy)
    while beat.loop():
        bitfinex_data = bitfinex.prices([BTC_USD, ETH_USD], "1m")
        kalman_fairs = kalman_strategy.tick(bitfinex_data)
        fairs = Gaussian.intersect([kalman_fairs])
        Log.info(fairs)
        executor.tick_fairs(fairs)


def dummy_main():
    while True:
        dummy_exchange.step_time()
        dummy_data = dummy_exchange.prices([BTC_USDT, ETH_USDT], "1m")
        # cointegration_fairs = cointegrator_strategy.step(dummy_data)
        kalman_fairs = kalman_strategy.tick(dummy_data)
        fairs = kalman_fairs & Gaussian(dummy_data["price"], [1e100 for _ in dummy_data["price"]])
        # executor.tick_fairs(cointegration_fairs)
        executor.tick_fairs(fairs)


thread_manager.attach("main", main, should_terminate=True)
# thread_manager.attach("dummy_main", dummy_main, should_terminate=True)
thread_manager.run()
