from trader.exchange.base import Exchange
from trader.constants import KRAKEN

from queue import Queue
from bitfinex import ClientV1, WssClient

import json
import krakenex
import time
import websocket as ws


class Bitfinex(Exchange):
    def __init__(self):
        super().__init__()
        self.name = Bitfinex
        self.bfx = ClientV1("UsuNjCcFLJjNvOwmKoaTWFmiGx1uV5ELrOZ6BwLxJrN",
                            "ra33x1guxsasZBE6YLCGhhtCyDCNPIBAAXMK0wtmpYO")
        self.wsclient = WssClient("UsuNjCcFLJjNvOwmKoaTWFmiGx1uV5ELrOZ6BwLxJrN",
                                  "ra33x1guxsasZBE6YLCGhhtCyDCNPIBAAXMK0wtmpYO")

        def do_nothing(blah):
            pass
        self.wsclient.authenticate(do_nothing)

    def _feed(self, pair, time_interval):
        candle_queue = Queue()

        def add_messages_to_queue(message):
            candle_queue.put(message)

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
            # responses, in that order.
            if (isinstance(message, list)
                    and isinstance(message[1], list)
                    and not isinstance(message[1][0], list)):
                yield message

    def add_order(self, pair, side, order_type, price, volume):
        return self.bfx.place_order(volume, price, side, order_type, pair)

    def cancel_order(self, order_id):
        return self.bfx.delete_order(order_id)

    def get_balance(self):
        return self.bfx.balances()

    def get_open_positions(self):
        return self.bfx.active_positions()
