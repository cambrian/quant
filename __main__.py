import pandas as pd

import trader.strategy as strategy
from trader import ExecutionStrategy, Executor, SignalAggregator
from trader.exchange import Bitfinex, DummyExchange
from trader.metrics import Metrics
from trader.util import Feed, Gaussian, Log
from trader.util.constants import (BINANCE, BTC, BTC_USD, BTC_USDT, ETH,
                                   ETH_USD, ETH_USDT, LTC_USDT, XRP_USDT)
from trader.util.thread import Beat, ThreadManager
from trader.util.types import Direction, ExchangePair, Order

pairs = [BTC_USD, ETH_USD]
thread_manager = ThreadManager()
# bitfinex = Bitfinex(thread_manager, pairs)
data_min = pd.read_hdf("research/data/1min.h5")

# dummy_strategy = strategy.Dummy()
window_size = 500
kalman_strategy = strategy.Kalman(
    window_size=window_size,
    movement_half_life=6,
    trend_half_life=256,
    cointegration_period=32,
    maxlag=8,
)
execution_strategy = ExecutionStrategy(size=10, min_edge=0.002, min_edge_to_close=0.0005)
# metrics = Metrics(thread_manager, {bitfinex})

aggregator = SignalAggregator(window_size, {"total_market": [BTC, ETH]})


def warmup():
    warmup_data = bitfinex.get_warmup_data(pairs, window_size, "1m")
    # TODO: conversion logic belongs in the exchange get_warmup_data fn. What goes here should be
    # related to stepping the strategy
    for i in range(0, len(warmup_data[pairs[0]])):
        tick_data = {}
        for pair in pairs:
            elem = warmup_data[pair][i]
            tick_data[ExchangePair(bitfinex.id, pair)] = (elem[1], elem[4])
        tick_data = pd.DataFrame.from_dict(tick_data, orient="index", columns=["price", "volume"])
        signals = aggregator.step(tick_data)
        kalman_strategy.tick(tick_data, signals)


def main():
    beat = Beat(60000)
    warmup()
    Log.info("Warmup Complete")

    executor = Executor(thread_manager, {bitfinex: pairs}, execution_strategy)
    while beat.loop():
        bitfinex_data = bitfinex.frame([BTC_USD, ETH_USD])
        signals = aggregator.step(bitfinex_data)
        kalman_fairs = kalman_strategy.tick(bitfinex_data, signals)
        fairs = Gaussian.intersect([kalman_fairs])
        Log.info(fairs)
        executor.tick_fairs(fairs)


def dummy_main():
    dummy_exchange = DummyExchange(
        thread_manager,
        BINANCE,
        data_min.resample("15Min").first(),
        {"maker": 0.00075, "taker": 0.00075},
    )
    executor = Executor(thread_manager, {dummy_exchange: [BTC_USDT, ETH_USDT]}, execution_strategy)
    while True:
        if not dummy_exchange.step_time():
            break
        dummy_data = dummy_exchange.frame([BTC_USDT, ETH_USDT])
        signals = aggregator.step(dummy_data)
        kalman_fairs = kalman_strategy.tick(dummy_data, signals)
        fairs = kalman_fairs & Gaussian(dummy_data["price"], [1e100 for _ in dummy_data["price"]])
        executor.tick_fairs(fairs)
    # TODO: analysis stuff


#     Log.info("final balances", executor.)


# thread_manager.attach("main", main, should_terminate=True)
thread_manager.attach("dummy_main", dummy_main, should_terminate=True)
thread_manager.run()
