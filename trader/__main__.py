# TODO: Add good docstring-style comments.
from bitfinex import ClientV1, WssClient
from exchange import Exchange
from executor import Executor
from queue import Queue
from strategy import Strategy
from util import manage_threads
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


class Bitfinex(Exchange):
    def __init__(self):
        self.bfx = ClientV1("UsuNjCcFLJjNvOwmKoaTWFmiGx1uV5ELrOZ6BwLxJrN",
                            "ra33x1guxsasZBE6YLCGhhtCyDCNPIBAAXMK0wtmpYO")
        self.wsclient = WssClient("UsuNjCcFLJjNvOwmKoaTWFmiGx1uV5ELrOZ6BwLxJrN",
                                  "ra33x1guxsasZBE6YLCGhhtCyDCNPIBAAXMK0wtmpYO")

        def do_nothing(blah):
            pass
        self.wsclient.authenticate(do_nothing)

    def _feed(self, pairs, time_interval):
        candle_queue = Queue()

        def add_messages_to_queue(message):
            candle_queue.put(message)

        for pair in pairs:
            self.wsclient.subscribe_to_candles(
                symbol=pair,
                timeframe=time_interval,
                callback=add_messages_to_queue
            )
        self.wsclient.start()
        time.sleep(5)

        while True:
            message = candle_queue.get()
            # Gross conditionals to avoid WS subscription events, heartbeats, and weird "catch-up"
            # respons, in that order.
            if (isinstance(message, list) and isinstance(message[1], list) and not isinstance(message[1][0], list)):
                yield message

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
        # # TODO: Strategy to derive fair estimate and stddev.
        print(data)
        print(data[1][5])
        fair = float(data[1][5])
        stddev = 100.0
        return ((fair, stddev), data)


kraken = Kraken()
bfx = Bitfinex()
strategy = DummyStrategy()
executor = DummyExecutor(bfx)
kraken_feed = kraken.observe(['XBT/USD'], 5)
bfx_feed = bfx.observe(['BTCUSD'], '1m')
kraken_strategy_feed = strategy.observe(kraken_feed)
bfx_strategy_feed = strategy.observe(bfx_feed)

# Lifecycle manager.
manage_threads(
    ('strategy-kraken', lambda: executor.consume(kraken_strategy_feed), True),
    ('strategy-bfx', lambda: executor.consume(bfx_strategy_feed), True),
    ('executor', lambda: executor.run(), True)
)
