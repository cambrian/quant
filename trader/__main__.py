from exchange import Exchange
from executor import Executor
from strategy import Strategy
from websocket import create_connection

import aiohttp
import asyncio
import time
import json


class Counter(Exchange):
    async def _feed(self, pairs, time_interval):
        counter = time_interval
        while True:
            yield counter
            await asyncio.sleep(1)
            counter += 1


class Kraken(Exchange):
    async def _feed(self, pairs, time_interval):
        for _ in range(3):
            try:
                self.session = aiohttp.ClientSession()
                self.ws = await self.session.ws_connect('wss://ws-sandbox.kraken.com')
            except Exception as error:
                print('caught error: ' + repr(error))
                time.sleep(3)
            else:
                break
        await self.ws.send_str(json.dumps({
            "event": "subscribe",
            "pair": pairs,
            "subscription": {
                "name": "ohlc",
                "interval": time_interval
            }
        }))

        while True:
            try:
                result = await self.ws.receive()
                # TODO: Error handling of this await.
                result = json.loads(result.data)
                # Ignore heartbeats.
                if not isinstance(result, dict):
                    yield result
            except Exception as error:
                print('caught error: ' + repr(error))
                time.sleep(3)


class DummyExecutor(Executor):
    async def _tick(self, fairs):
        print(fairs)


class DummyStrategy(Strategy):
    def _tick(self, data):
        return str(data)


counter = Counter()
exchange = Kraken()
strategy = DummyStrategy()
executor = DummyExecutor()
counter_feed = counter.observe([], 1)
exchange_feed = exchange.observe(['XBT/USD'], 5)
strategy_feed = strategy.process(exchange_feed)


async def main():
    await asyncio.gather(
        executor.consume(counter_feed),
        executor.consume(strategy_feed)
    )


asyncio.run(main())
