import json

import pandas as pd

import trader.strategy as strategy
from trader import ExecutionStrategy, Executor, SignalAggregator
from trader.exchange import Bitfinex, DummyExchange
from trader.metrics import Metrics
from trader.util import Gaussian, Log
from trader.util.constants import (BCH_USD, BINANCE, BSV_USD, BTC_USD,
                                   BTC_USDT, EOS_USD, EOS_USDT, ETH_USD,
                                   ETH_USDT, LTC_USD, LTC_USDT, NEO_USDT,
                                   XRP_USD, XRP_USDT)
from trader.util.thread import Beat, ThreadManager

# should this be a global that lives in trader.util.thread?
THREAD_MANAGER = ThreadManager()


def warmup(exchange, pairs, strategy, signal_aggregator, window_size):
    Log.info("Warming up strategy from recent data...")
    warmup_data = exchange.get_warmup_data(pairs, window_size, "1m")
    for row in warmup_data:
        signals = signal_aggregator.step(row)
        strategy.tick(row, signals)


def main():
    pairs = [BTC_USD, ETH_USD, XRP_USD, LTC_USD, EOS_USD, BCH_USD, BSV_USD]

    window_size = 7500
    kalman_strategy = strategy.Kalman(
        window_size=window_size,
        movement_hl=90,
        trend_hl=3000,
        variance_hl=2880,
        cointegration_period=60,
        maxlag=120,
    )
    execution_strategy = ExecutionStrategy(1000, 2880, 3, 10, -1, 0.002, 0.0005)
    aggregator = SignalAggregator(window_size, {"total_market": [p.base for p in pairs]})
    with open("keys/bitfinex.json") as bitfinex_key_file:
        bitfinex_keys = json.load(bitfinex_key_file)
    bitfinex = Bitfinex(THREAD_MANAGER, bitfinex_keys, pairs)
    executor = Executor(THREAD_MANAGER, {bitfinex: pairs}, execution_strategy)
    warmup(bitfinex, pairs, kalman_strategy, aggregator, window_size)

    beat = Beat(60000)
    while beat.loop():
        Log.info("Beat")
        bfx_frame = bitfinex.frame(pairs)
        signals = aggregator.step(bfx_frame)
        kalman_fairs = kalman_strategy.tick(bfx_frame, signals)
        fairs = kalman_fairs & Gaussian(bfx_frame["price"], [1e100 for _ in bfx_frame["price"]])
        Log.info("fairs", fairs)
        executor.tick_fairs(fairs)


def dummy_main():
    pairs = [BTC_USDT, ETH_USDT, XRP_USDT, LTC_USDT, NEO_USDT, EOS_USDT]

    window_size = 500
    kalman_strategy = strategy.Kalman(
        window_size=window_size,
        movement_hl=6,
        trend_hl=256,
        variance_hl=192,
        cointegration_period=32,
        maxlag=8,
    )
    execution_strategy = ExecutionStrategy(10, 192, 1, 3, -0.5, 0.002, 0.0005)
    aggregator = SignalAggregator(window_size, {"total_market": [p.base for p in pairs]})

    data_min = pd.read_hdf("research/data/1min.h5")
    dummy_exchange = DummyExchange(
        THREAD_MANAGER,
        BINANCE,
        data_min.resample("15Min").first(),
        {"maker": 0.00075, "taker": 0.00075},
    )
    executor = Executor(THREAD_MANAGER, {dummy_exchange: pairs}, execution_strategy)
    while True:
        if not dummy_exchange.step_time():
            break
        dummy_data = dummy_exchange.frame(pairs)
        signals = aggregator.step(dummy_data)
        kalman_fairs = kalman_strategy.tick(dummy_data, signals)
        fairs = kalman_fairs & Gaussian(dummy_data["price"], [1e100 for _ in dummy_data["price"]])
        Log.info("fairs", fairs)
        executor.tick_fairs(fairs)
    # TODO: analysis stuff


#     Log.info("final positions", executor.)


THREAD_MANAGER.attach("main", main, should_terminate=True)
# THREAD_MANAGER.attach("dummy_main", dummy_main, should_terminate=True)
THREAD_MANAGER.run()
