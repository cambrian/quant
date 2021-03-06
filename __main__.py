import json

import pandas as pd

import trader.strategy as strategy
from trader import ExecutionStrategy, Executor, SignalAggregator, UsdConverter
from trader.exchange import Bitfinex, DummyExchange
from trader.util import Gaussian, Log
from trader.util.constants import (BCH_USD, BINANCE, BSV_USD, BTC_USD,
                                   BTC_USDT, EOS_USD, EOS_USDT, ETH_USD,
                                   ETH_USDT, LTC_USD, LTC_USDT, NEO_USDT,
                                   XRP_USD, XRP_USDT)
from trader.util.thread import Beat, ThreadManager

# should this be a global that lives in trader.util.thread?
THREAD_MANAGER = ThreadManager()


def main():
    pairs = [BTC_USD, ETH_USD, XRP_USD, LTC_USD, EOS_USD, BCH_USD, BSV_USD]
    window_size = 9999  # biggest window that will fit in 2 api calls to candles

    Log.info("Connecting to exchanges.")
    with open("keys/bitfinex.json") as bitfinex_key_file:
        bitfinex_keys = json.load(bitfinex_key_file)
    bitfinex = Bitfinex(THREAD_MANAGER, bitfinex_keys, pairs)

    Log.info("Fetching warmup data.")
    warmup_data = bitfinex.get_warmup_data(pairs, window_size, "1m")

    Log.info("Prepping warmup data.")
    converter = UsdConverter()
    aggregator = SignalAggregator(window_size, {"total_market": [p.base for p in pairs]})
    warmup_data = warmup_data.apply(converter.step, axis=1)
    warmup_signals = warmup_data.apply(aggregator.step, axis=1)

    Log.info("Initializing components.")
    kalman_strategy = strategy.Kalman(
        window_size=window_size,
        movement_hl=1440 * 3,
        trend_hl=window_size,
        cointegration_period=720,
        warmup_signals=warmup_signals,
        warmup_data=warmup_data,
    )
    execution_strategy = ExecutionStrategy(500, 1, 3, 45, 135, 60, 180, warmup_data)
    executor = Executor(THREAD_MANAGER, {bitfinex: pairs}, execution_strategy)

    beat = Beat(60000)
    while beat.loop():
        Log.info("Beat")
        bfx_frame = bitfinex.frame(pairs)
        frame_usd = converter.step(bfx_frame)
        signals = aggregator.step(frame_usd)
        kalman_fairs = kalman_strategy.tick(frame_usd, signals)
        fairs = kalman_fairs & Gaussian(
            frame_usd.xs("price", level=1), [1e100 for _ in frame_usd.xs("price", level=1).index]
        )
        Log.info("fairs", fairs)
        executor.tick_fairs(fairs)


def dummy_main():
    pairs = [BTC_USDT, ETH_USDT, XRP_USDT, LTC_USDT, NEO_USDT, EOS_USDT]
    Log.info("Loading dummy data.")
    data = pd.read_hdf("research/data/1min.h5")
    data = data.resample("15Min").first()
    window_size = 500

    converter = UsdConverter()
    aggregator = SignalAggregator(window_size, {"total_market": [p.base for p in pairs]})
    Log.info("Processing warmup data.")
    warmup_data = data.iloc[:window_size]
    data = data.iloc[window_size:]
    warmup_data = warmup_data.apply(converter.step, axis=1)
    warmup_signals = warmup_data.apply(aggregator.step, axis=1)

    Log.info("Initializing components.")
    kalman_strategy = strategy.Kalman(
        window_size=window_size,
        movement_hl=288,
        trend_hl=256,
        cointegration_period=96,
        warmup_signals=warmup_signals,
        warmup_data=warmup_data,
    )
    # use same params for trend and micro trend because 15min is too wide for micro trends to have
    # effect
    execution_strategy = ExecutionStrategy(10, 3, 9, 3, 9, 4, 12, warmup_data)

    dummy_exchange = DummyExchange(
        THREAD_MANAGER, BINANCE, data, {"maker": 0.00075, "taker": 0.00075}
    )
    executor = Executor(THREAD_MANAGER, {dummy_exchange: pairs}, execution_strategy)
    while True:
        if not dummy_exchange.step_time():
            break
        frame = dummy_exchange.frame(pairs)
        frame_usd = converter.step(frame)
        signals = aggregator.step(frame_usd)
        kalman_fairs = kalman_strategy.tick(frame_usd, signals)
        fairs = kalman_fairs & Gaussian(
            frame_usd.xs("price", level=1), [1e100 for _ in frame_usd.xs("price", level=1).index]
        )
        Log.info("fairs", fairs)
        executor.tick_fairs(fairs)
    # TODO: analysis stuff


#     Log.info("final positions", executor.)


THREAD_MANAGER.attach("main", main, should_terminate=True)
# THREAD_MANAGER.attach("dummy_main", dummy_main, should_terminate=True)
THREAD_MANAGER.run()
