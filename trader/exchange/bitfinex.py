import os
import time
from queue import Queue

import pandas as pd
from bitfinex import ClientV1, ClientV2, WssClient

from trader.exchange.base import Exchange
from trader.util.constants import BTC_USD, ETH_USD, XRP_USD


class Bitfinex(Exchange):
    """The Bitfinex exchange.

    Store your API key and secret in the `BITFINEX_API_KEY` and `BITFINEX_SECRET` environment
    variables.

    """

    def __init__(self):
        super().__init__()
        self.bfxv1 = ClientV1(os.getenv('BITFINEX_API_KEY', ''),
                              os.getenv('BITFINEX_SECRET', ''))
        self.bfxv2 = ClientV2(os.getenv('BITFINEX_API_KEY', ''),
                              os.getenv('BITFINEX_SECRET', ''))
        self.ws_client = WssClient(os.getenv('BITFINEX_API_KEY', ''),
                                   os.getenv('BITFINEX_SECRET', ''))
        self.ws_client.authenticate(lambda x: None)
        self.ws_client.daemon = True
        self.translate = {
            BTC_USD: 'tBTCUSD',
            ETH_USD: 'tETHUSD',
            XRP_USD: 'tXRPUSD'
        }

    def _book(self, pair):
        # TODO: Update orderbook on each.get() rather than just yield message
        pair = self.translate[pair]
        book_queue = Queue()

        def add_messages_to_queue(message):
            # Ignore status/subscription dicts
            if (isinstance(message, list)):
                book_queue.put(message)

        self.ws_client.subscribe_to_orderbook(
            pair,
            precision='R0',
            callback=add_messages_to_queue
        )
        self.ws_client.start()
        # Current state of order_book is always first message
        raw_book = book_queue.get()[1]
        order_book = {}
        for order in raw_book:
            side = 'bid' if order[2] > 0 else 'ask'
            order_book[order[0]] = (side, order[1], abs(order[2]))

        while True:
            yield pd.DataFrame(order_book.values(), columns=['Side', 'Price', 'Volume'])
            change = book_queue.get()
            if len(change) > 1:
                # Order was filled
                if change[1][1] == 0:
                    if change[1][0] in order_book:
                        order_book.pop(change[1][0], None)
                else:
                    side = 'bid' if change[1][2] > 0 else 'ask'
                    order_book[change[1][0]] = (side, change[1][1], abs(change[1][2]))

    # time_frame expected as string rep: '1m', '5m', '1h', etc.
    def prices(self, pairs, time_frame):
        data = {
            'Close': [],
            'Volume': []
        }
        for pair in pairs:
            pair = self.translate[pair]
            # Ignore index [0] timestamp
            ochlv = self.bfxv2.candles(time_frame, pair, "last")[1:]
            data['Close'].append(ochlv[1])
            data['Volume'].append(ochlv[4])
        return pd.DataFrame.from_dict(data, orient='index', columns=pairs)

    def add_order(self, pair, side, order_type, price, volume, maker=False):
        payload = {
            "request": "/v1/order/new",
            "nonce": self.bfxv1._nonce(),
            "symbol": pair,
            "amount": volume,
            "price": price,
            "exchange": "bitfinex",
            "side": side,
            "type": order_type,
            "is_postonly": maker
        }
        return self.bfxv1._post("/order/new", payload=payload, verify=True)

    def cancel_order(self, order_id):
        return self.bfxv1.delete_order(order_id)

    def get_balance(self):
        return self.bfxv1.balances()

    def get_open_positions(self):
        return self.bfxv1.active_orders()
