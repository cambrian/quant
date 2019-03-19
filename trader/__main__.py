# TODO: See if we actually need multiple "threads" of operation (if not, we can remove asyncio).
from exchange import Exchange
from executor import Executor
from strategy import Strategy
from util import call_async

from concurrent.futures import ThreadPoolExecutor
from websocket import create_connection

import aiohttp
import asyncio
import json
import krakenex
import time


class Kraken(Exchange):
    # TODO: Get real Kraken account w/ KYC and money.
    def __init__(self):
        self.kraken = krakenex.API()
        # self.kraken.load_key('secret.key')

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
            'event': 'subscribe',
            'pair': pairs,
            'subscription': {
                'name': 'ohlc',
                'interval': time_interval
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

    async def add_order(self, pair, side, order_type, price, volume):
        await call_async(lambda: self.kraken.query_private('AddOrder', {
            'pair': pair,
            'type': side,
            'ordertype': order_type,
            'price': price,
            'volume': volume
        }))

    async def cancel_order(self, order_id):
        await call_async(lambda: self.kraken.query_private('CancelOrder', {
            'txid': order_id
        }))

    async def get_balance(self):
        await call_async(lambda: self.kraken.query_private('Balance'))

    async def get_open_positions(self):
        await call_async(lambda: self.kraken.query_private('OpenPositions'))


class DummyExecutor(Executor):
    def __init__(self, exchange):
        self.exchange = exchange

    async def _tick(self, fairs):
        close = float(fairs[1][5])
        print('Close: {}'.format(close))
        if close < 3900:
            print('Buying 1 BTC at {}.'.format(close))
            await self.exchange.add_order('XXBTZUSD', 'buy', 'market', close, 1)
        elif close > 3950:
            print('Selling 1 BTC at {}.'.format(close))
            await self.exchange.add_order('XXBTZUSD', 'sell', 'market', close, 1)


class DummyStrategy(Strategy):
    def _tick(self, data):
        return data


exchange = Kraken()
strategy = DummyStrategy()
executor = DummyExecutor(exchange)
exchange_feed = exchange.observe(['XBT/USD'], 5)
strategy_feed = strategy.observe(exchange_feed)

# To add more async tasks, create a co-routine with a call to `async.gather`.
asyncio.run(executor.consume(strategy_feed))
