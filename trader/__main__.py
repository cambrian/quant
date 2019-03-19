from exchange import Exchange
from executor import Executor
from strategy import Strategy

import asyncio
import time


class DummyExchange(Exchange):
    def _feed(self, pairs, time_interval):
        counter = 1
        while True:
            time.sleep(1)
            yield counter
            counter += 1


class DummyExecutor(Executor):
    async def _tick(self, fairs):
        print(fairs)


class DummyStrategy(Strategy):
    def _tick(self, data):
        return str(data)


exchange = DummyExchange()
strategy = DummyStrategy()
executor = DummyExecutor()
exchange_feed = exchange.observe([], 0)
strategy_feed = strategy.process(exchange_feed)
asyncio.run(executor.consume(strategy_feed))
