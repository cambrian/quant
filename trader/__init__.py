"""The `trader` module.

A production framework for running quantitative strategies.

"""
from trader.execution_strategy import ExecutionStrategy
from trader.executor import Executor
from trader.signal_aggregator import SignalAggregator
from trader.strategy import Strategy
from trader.usd_converter import UsdConverter
