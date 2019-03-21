# TODO: Add good docstring-style comments.
from bitfinex import ClientV1, WssClient
from exchange import Exchange
from executor import Executor
from queue import Queue
from strategy import Strategy
from threading import Thread
from util import run_threads_forever

import json
import krakenex
import time
import websocket as ws


class Kraken(Exchange):
    # TODO: Get real Kraken account w/ KYC and money.
    def __init__(self):
        self.kraken = krakenex.API()
        # self.kraken.load_key('secret.key')

    def _feed(self, pairs, time_interval):
        for _ in range(3):
            try:
                self.ws = ws.create_connection('wss://ws-sandbox.kraken.com')
            except Exception as error:
                print('caught error: ' + repr(error))
                time.sleep(3)
            else:
                break
        self.ws.send(json.dumps({
            'event': 'subscribe',
            'pair': pairs,
            'subscription': {
                'name': 'ohlc',
                'interval': time_interval
            }
        }))

        while True:
            try:
                result_raw = self.ws.recv()
                # TODO: Error handling of this await.
                result = json.loads(result_raw)
                # Ignore heartbeats.
                if not isinstance(result, dict):
                    yield result
            except Exception as error:
                print('caught error: ' + repr(error))
                time.sleep(3)

    def add_order(self, pair, side, order_type, price, volume):
        self.kraken.query_private('AddOrder', {
            'pair': pair,
            'type': side,
            'ordertype': order_type,
            'price': price,
            'volume': volume
        })

    def cancel_order(self, order_id):
        self.kraken.query_private('CancelOrder', {
            'txid': order_id
        })

    def get_balance(self):
        self.kraken.query_private('Balance')

    def get_open_positions(self):
        self.kraken.query_private('OpenPositions')


class Bitfinex(Exchange):
    def __init__(self):
        self.bfx = ClientV1("UsuNjCcFLJjNvOwmKoaTWFmiGx1uV5ELrOZ6BwLxJrN",
                            "ra33x1guxsasZBE6YLCGhhtCyDCNPIBAAXMK0wtmpYO")
        self.wsclient = WssClient("UsuNjCcFLJjNvOwmKoaTWFmiGx1uV5ELrOZ6BwLxJrN",
                                  "ra33x1guxsasZBE6YLCGhhtCyDCNPIBAAXMK0wtmpYO")
        self.wsclient.authenticate(print)

    def _feed(self, pairs, time_interval):

        pass

    def add_order(self, pair, side, order_type, price, volume):
        return self.bfx.place_order(volume, price, side, order_type, pair)

    def cancel_order(self, order_id):
        return self.bfx.delete_order(order_id)

    def get_balance(self):
        return self.bfx.balances()

    def get_open_positions(self):
        return self.bfx.active_positions()


class DummyExecutor(Executor):
    def __init__(self, exchange):
        super().__init__()
        self.exchange = exchange

    def _tick(self, input):
        ((fair, stddev), data) = input
        close = float(data[1][5])
        print('Close: {}, Fair: {}, Stddev: {}'.format(close, fair, stddev))
        if close < fair - stddev:
            print('Buying 1 BTC at {}.'.format(close))
            # self.exchange.add_order('XXBTZUSD', 'buy', 'market', close, 1)
        elif close > fair + stddev:
            print('Selling 1 BTC at {}.'.format(close))
            # self.exchange.add_order('XXBTZUSD', 'sell', 'market', close, 1)


class DummyStrategy(Strategy):
    def _tick(self, data):
        # TODO: Strategy to derive fair estimate and stddev.
        fair = float(data[1][5])
        stddev = 100.0
        return ((fair, stddev), data)


exchange = Kraken()
strategy = DummyStrategy()
executor = DummyExecutor(exchange)
exchange_feed = exchange.observe(['XBT/USD'], 5)
strategy_feed = strategy.observe(exchange_feed)
bfx = Bitfinex()
wsclient = WssClient("UsuNjCcFLJjNvOwmKoaTWFmiGx1uV5ELrOZ6BwLxJrN",
                     "ra33x1guxsasZBE6YLCGhhtCyDCNPIBAAXMK0wtmpYO")
wsclient.authenticate(print)


def my_candle_handler(message):
    print(message)


wsclient.subscribe_to_candles(
    symbol='BTCUSD',
    timeframe='1m',
    callback=my_candle_handler
)

# # Thread manager.
# run_threads_forever(
#     ('strategy', lambda: executor.consume(strategy_feed)),
#     ('executor', lambda: executor.run())
# )
