from exchange import Exchange
from executor import Executor
from strategy import Strategy
from websocket import create_connection
import krakenex

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

    def add_order(self, pair, side, ordertype, price, volume):
        pass

    def cancel_order(self, order_id):
        pass

    def get_balance(self):
        pass

    def get_open_positions(self):
        pass


class Kraken(Exchange):
    # TODO: Get real Kraken account w/ KYC and money
    def __init__(self):
        self.kraken = krakenex.API()
        self.kraken.load_key("secret.key")

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

    def add_order(self, pair, side, ordertype, price, volume):
        return self.kraken.query_private("AddOrder",
                                         {
                                             "pair": pair,
                                             "type": side,
                                             "ordertype": ordertype,
                                             "price": price,
                                             "volume": volume
                                         })

    def cancel_order(self, order_id):
        return self.kraken.query_private("CancelOrder",
                                         {
                                             "txid": order_id
                                         })

    def get_balance(self):
        return self.kraken.query_private("Balance")

    def get_open_positions(self):
        return self.kraken.query_private("OpenPositions")


class DummyExecutor(Executor):
    async def _tick(self, fairs):
        close = float(fairs[1][5])
        print(close)
        if close < 3900:
            print("Buying 1 BTC at ", close)
            self.exchange.add_order("XXBTZUSD", "buy", "market", close, 1)
        elif close > 3950:
            print("Selling 1 BTC at ", close)
            self.exchange.add_order("XXBTZUSD", "sell", "market", close, 1)


class DummyStrategy(Strategy):
    def _tick(self, data):
        return data


exchange = Kraken()
strategy = DummyStrategy()
executor = DummyExecutor()
exchange_feed = exchange.observe(['XBT/USD'], 5)
strategy_feed = strategy.process(exchange_feed)


async def main():
    await asyncio.gather(
        executor.consume(strategy_feed, exchange)
    )


asyncio.run(main())
