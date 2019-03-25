from trader.exchange.base import Exchange
from trader.util.constants import BITFINEX

from datetime import datetime
from queue import Queue
from bitfinex import ClientV1, WssClient

import json
import krakenex
import os
import time
import websocket as ws


class Bitfinex(Exchange):
    """The Bitfinex exchange.

    Store your API key and secret in the `BITFINEX_API_KEY` and `BITFINEX_SECRET` environment
    variables.

    """

    def __init__(self):
        super().__init__()
        self.bfx = ClientV1(os.getenv('BITFINEX_API_KEY', ''),
                            os.getenv('BITFINEX_SECRET', ''))
        self.ws_client = WssClient(os.getenv('BITFINEX_API_KEY', ''),
                                   os.getenv('BITFINEX_SECRET', ''))
        self.ws_client.authenticate(lambda x: None)
        self.ws_client.daemon = True

    def _feed(self, pair, time_interval):
        candle_queue = Queue()

        def add_messages_to_queue(message):
            candle_queue.put(message)

        self.ws_client.subscribe_to_candles(
            symbol=pair,
            timeframe=time_interval,
            callback=add_messages_to_queue
        )

        self.ws_client.start()
        time.sleep(5)

        while True:
            message = candle_queue.get()
            # Gross conditionals to avoid WS subscription events, heartbeats, and weird "catch-up"
            # responses, in that order.
            if (isinstance(message, list)
                    and isinstance(message[1], list)
                    and not isinstance(message[1][0], list)):
                ohlcv = {}
                ohlcv['timestamp'] = datetime.now()
                ohlcv['open'] = message[1][1]
                ohlcv['high'] = message[1][3]
                ohlcv['low'] = message[1][4]
                ohlcv['close'] = message[1][2]
                ohlcv['volume'] = message[1][5]
                yield ohlcv

    def add_order(self, pair, side, order_type, price, volume):
        return self.bfx.place_order(volume, price, side, order_type, pair)

    def cancel_order(self, order_id):
        return self.bfx.delete_order(order_id)

    def get_balance(self):
        return self.bfx.balances()

    def get_open_positions(self):
        # return self.bfx.active_positions()
        return self.bfx.active_orders()
