from exchange import Exchange
from executor import Executor
from strategy import Strategy
from websocket import create_connection

import asyncio
import time
import json


class DummyExchange(Exchange):
    def _feed(self, pairs, time_interval):
        counter = 1
        while True:
            time.sleep(1)
            yield counter
            counter += 1


class Kraken(Exchange):
    # TODO: Update to be async ?
    def _feed(self, pairs, time_interval):
        for _ in range(3):
            try:
                self.ws = create_connection("wss://ws-sandbox.kraken.com")
            except Exception as error:
                print('Caught this error: ' + repr(error))
                time.sleep(3)
            else:
                break
        self.ws.send(json.dumps({
            "event": "subscribe",
            "pair": pairs,
            "subscription": {
                "name": "ohlc",
                "interval": time_interval
            }
        }))

        while True:
            try:
                result = self.ws.recv()
                result = json.loads(result)
                # Ignore heartbeats
                if not isinstance(result, dict):
                    yield result
            except Exception as error:
                print('Caught this error: ' + repr(error))
                time.sleep(3)


class DummyExecutor(Executor):
    async def _tick(self, fairs):
        print(fairs)


class DummyStrategy(Strategy):
    def _tick(self, data):
        return str(data)


# exchange = DummyExchange()
exchange = Kraken()
strategy = DummyStrategy()
executor = DummyExecutor()
exchange_feed = exchange.observe(["XBT/USD"], 5)
strategy_feed = strategy.process(exchange_feed)
asyncio.run(executor.consume(strategy_feed))
