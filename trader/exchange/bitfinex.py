import os
import time
from queue import Queue

import pandas as pd
from bitfinex import ClientV1, ClientV2, WssClient
from sortedcontainers import SortedList

from trader.exchange.base import Exchange
from trader.util.constants import BITFINEX, BTC_USD, ETH_USD, XRP_USD


class Bitfinex(Exchange):
    """The Bitfinex exchange.

    Store your API key and secret in the `BITFINEX_API_KEY` and `BITFINEX_SECRET` environment
    variables.

    """

    def __init__(self):
        super().__init__()
        self.__bfxv1 = ClientV1(
            os.getenv("BITFINEX_API_KEY", ""), os.getenv("BITFINEX_SECRET", "")
        )
        self.__bfxv1 = ClientV2(
            os.getenv("BITFINEX_API_KEY", ""), os.getenv("BITFINEX_SECRET", "")
        )
        self.__ws_client = WssClient(
            os.getenv("BITFINEX_API_KEY", ""), os.getenv("BITFINEX_SECRET", "")
        )
        self.__ws_client.authenticate(lambda x: None)
        self.__ws_client.daemon = True
        self.__translate = {BTC_USD: "tBTCUSD", ETH_USD: "tETHUSD", XRP_USD: "tXRPUSD"}
        # TODO: Can this be dynamically loaded? (For other exchanges too.)
        self.__fees = {"maker": 0.001, "taker": 0.002}

    @property
    def fees(self):
        return self.__fees

    def _book(self, pair):
        trans_pair = self.__translate[pair]
        book_queue = Queue()

        def add_messages_to_queue(message):
            # Ignore status/subscription dicts.
            if isinstance(message, list):
                book_queue.put(message)

        self.__ws_client.subscribe_to_orderbook(
            trans_pair, precision="R0", callback=add_messages_to_queue
        )
        self.__ws_client.start()

        # Current state of `order_book` is always first message.
        raw_book = book_queue.get()[1]
        order_book = {
            "bid": SortedList(key=lambda x: -x[0]),
            "ask": SortedList(key=lambda x: x[0]),
        }
        for order in raw_book:
            if order[2] > 0:
                order_book["bid"].add((order[1], abs(order[2]), order[0]))
            else:
                order_book["ask"].add((order[1], abs(order[2]), order[0]))

        while True:
            # TODO: Change this to yield more information in the future if necessary.
            yield (BITFINEX, pair, (order_book["bid"][0], order_book["ask"][0]))
            change = book_queue.get()
            delete = False
            if len(change) > 1 and isinstance(change[1], list):
                side = "bid" if change[1][2] > 0 else "ask"
                # Order was filled:
                for order in order_book[side]:
                    if order[2] == change[1][0]:
                        order_book[side].discard(order)
                        if change[1][1] == 0:
                            delete = True
                        break
                if not delete:
                    order_book[side].add(
                        (change[1][1], abs(change[1][2]), change[1][0])
                    )

    def prices(self, pairs, time_frame):
        """

        NOTE: `time_frame` expected as Bitfinex-specific string representation (e.g. '1m').

        """
        data = {"close": [], "volume": []}
        for pair in pairs:
            pair = self.__translate[pair]
            # Ignore index [0] timestamp.
            ochlv = self.__bfxv1.candles(time_frame, pair, "last")[1:]
            data["close"].append(ochlv[1])
            data["volume"].append(ochlv[4])
        return pd.DataFrame.from_dict(data, orient="index", columns=pairs)

    def add_order(self, pair, side, order_type, price, volume, maker=False):
        payload = {
            "request": "/v1/order/new",
            "nonce": self.__bfxv1._nonce(),
            "symbol": pair,
            "amount": volume,
            "price": price,
            "exchange": "bitfinex",
            "side": side,
            "type": order_type,
            "is_postonly": maker,
        }
        return self.__bfxv1._post("/order/new", payload=payload, verify=True)

    def cancel_order(self, order_id):
        return self.__bfxv1.delete_order(order_id)

    def get_balance(self):
        balances = {}
        for row in self.__bfxv1.balances():
            # TODO: Use dynamically-updated data from running `self.balance`.
            if row["type"] == "exchange":
                balances[row["currency"].upper()] = row["available"]
        return balances

    def get_open_positions(self):
        return self.__bfxv1.active_orders()
