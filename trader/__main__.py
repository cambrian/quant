# TODO: Add good docstring-style comments.
from exchange import Exchange
from executor import Executor
from strategy import Strategy
from util import run_threads_forever

from threading import Thread

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

# Thread manager.
run_threads_forever(
    ('strategy', lambda: executor.consume(strategy_feed)),
    ('executor', lambda: executor.run())
)
