import hashlib
import hmac
import json
import os
import time
from collections import defaultdict
from queue import Queue

import pandas as pd
from bitfinex import ClientV1, ClientV2, WssClient
from sortedcontainers import SortedList
from websocket import WebSocketApp

from trader.exchange.base import Exchange, ExchangeError
from trader.util.constants import BITFINEX, BTC, BTC_USD, ETH, ETH_USD, USD, XRP, XRP_USD
from trader.util.feed import Feed
from trader.util.log import Log
from trader.util.types import Direction, Order, OrderBook


class Bitfinex(Exchange):
    """The Bitfinex exchange.

    Store your API key and secret in the `BITFINEX_API_KEY` and `BITFINEX_SECRET` environment
    variables.

    """

    # Allow only 1 instance. In the near future we should change the exchange classes to actually
    # be singletons, but first we should extract common logic into the Exchange base class before
    # making that change.
    __instance_exists = False

    def __init__(self, thread_manager):
        assert not Bitfinex.__instance_exists
        Bitfinex.__instance_exists = True
        super().__init__(thread_manager)
        self.__api_key = os.getenv("BITFINEX_API_KEY", "")
        self.__api_secret = os.getenv("BITFINEX_SECRET", "")
        self.__bfxv1 = ClientV1(self.__api_key, self.__api_secret)
        self.__bfxv2 = ClientV2(self.__api_key, self.__api_secret)
        self.__ws_client = WssClient(self.__api_key, self.__api_secret)
        self.__ws_client.authenticate(lambda x: None)
        self.__ws_client.daemon = True
        self.__translate_to = {BTC_USD: "tBTCUSD", ETH_USD: "tETHUSD", XRP_USD: "tXRPUSD"}
        self.__translate_from = {"USD": USD, "BTC": BTC, "ETH": ETH, "XRP": XRP}
        self.__supported_pairs = self.__translate_to
        self.__order_types = {
            Order.Type.MARKET: "exchange market",
            Order.Type.LIMIT: "exchange limit",
            Order.Type.IOC: "exchange immediate-or-cancel",
            Order.Type.FOK: "exchange fill-or-kill",
        }
        # TODO: Can this be dynamically loaded? (For other exchanges too.)
        self.__fees = {"maker": 0.001, "taker": 0.002}
        self.__books = {}
        self.__prices = {}
        self.__balances = defaultdict(float)
        thread_manager.attach("bitfinex-balances", self.__track_balances)
        # TODO: Maybe start this in a lazy way?
        self.__ws_client.start()

    @property
    def id(self):
        return BITFINEX

    def book(self, pair):
        if pair not in self.__supported_pairs:
            raise ExchangeError("pair not supported by Bitfinex")
        if pair in self.__books:
            return self.__books[pair]
        else:
            pair_feed, runner = Feed.of(self.__book(pair))
            self._thread_manager.attach("bitfinex-{}-book".format(pair), runner)
            self.__books[pair] = pair_feed
            return pair_feed

    def __book(self, pair):
        trans_pair = self.__translate_to[pair]
        book_queue = Queue()

        def add_messages_to_queue(message):
            # Ignore status/subscription dicts.
            if isinstance(message, list):
                book_queue.put(message)

        def handle_snapshot(snapshot):
            order_book = {
                "bid": SortedList(key=lambda x: -x[0]),
                "ask": SortedList(key=lambda x: x[0]),
            }
            for order in snapshot:
                if order[2] > 0:
                    order_book["bid"].add((order[1], abs(order[2]), order[0]))
                else:
                    order_book["ask"].add((order[1], abs(order[2]), order[0]))
            return order_book

        self.__ws_client.subscribe_to_orderbook(
            trans_pair, precision="R0", callback=add_messages_to_queue
        )
        last_trade_price = None

        raw_book = book_queue.get()[1]
        order_book = handle_snapshot(raw_book)

        while True:
            yield OrderBook(
                self,
                pair,
                last_trade_price,
                order_book["bid"][0][0] if len(order_book["bid"]) > 0 else None,
                order_book["ask"][0][0] if len(order_book["ask"]) > 0 else None,
            )
            change = book_queue.get()
            # If WS has been reset (such that we are getting a snapshot back), update order_book
            # with current snapshot:
            if len(change) > 2 and isinstance(change[0], list):
                order_book = handle_snapshot(change)
            # Else handle update normally:
            else:
                delete = False
                if len(change) > 1 and isinstance(change[1], list):
                    for side in ["bid", "ask"]:
                        for order in order_book[side]:
                            if order[2] == change[1][0]:
                                # Order was filled:
                                if change[1][1] == 0:
                                    delete = True
                                    last_trade_price = float(order[0])
                                order_book[side].discard(order)
                                break
                        if not delete:
                            order_book[side].add((change[1][1], abs(change[1][2]), change[1][0]))

    def prices(self, pairs, time_frame):
        """

        NOTE: `time_frame` expected as Bitfinex-specific string representation (e.g. '1m').

        """
        data = {"close": [], "volume": []}
        for pair in pairs:
            if pair not in self.__supported_pairs:
                raise ExchangeError("pair not supported by Bitfinex")
            if pair in self.__prices:
                pair_last_price = self.__prices[pair]
            else:
                pair_feed = self.book(pair)
                pair_last_price, runner = pair_feed.fold(lambda book, _: book.last_price, None)
                self.__prices[pair] = pair_last_price
                self._thread_manager.attach("bitfinex-{}-last-price".format(pair), runner)

            pair = self.__translate_to[pair]
            # Ignore index [0] timestamp.
            # NOTE: Careful with this call; Bitfinex rate limits pretty aggressively.
            ochlv = self.__bfxv2.candles(time_frame, pair, "last")[1:]
            data["close"].append(pair_last_price.read())
            # TODO: Is this volume lagged?
            data["volume"].append(ochlv[4])
        return pd.DataFrame.from_dict(data, orient="index", columns=pairs)

    @property
    def balances(self):
        return self.__balances

    def __track_balances(self):
        """Thread function to constantly track exchange's balance."""

        def on_open(ws):
            nonce = int(time.time() * 1000000)
            auth_payload = "AUTH{}".format(nonce)
            signature = hmac.new(
                self.__api_secret.encode(), msg=auth_payload.encode(), digestmod=hashlib.sha384
            ).hexdigest()

            payload = {
                "apiKey": self.__api_key,
                "event": "auth",
                "authPayload": auth_payload,
                "authNonce": nonce,
                "authSig": signature,
                "filter": ["wallet"],
            }
            ws.send(json.dumps(payload))

        def on_message(ws, msg):
            msg = json.loads(msg)

            def update_balances(update):
                # Only track exchange (trading) wallet.
                if len(update) >= 3 and update[0] == "exchange":
                    self.__balances[self.__translate_from[update[1]]] = update[2]

            if isinstance(msg, list):
                # Ignore heartbeats.
                if len(msg) > 1 and msg[1] != "hb":
                    # Disambiguate wallet snapshot/update:
                    if msg[1] == "ws":
                        for update in msg[2]:
                            update_balances(update)
                    elif msg[1] == "wu":
                        update_balances(msg[2])

        def on_error(ws, error):
            Log.warn("WS error within __track_balances for exchange {}: {}".format(self.id, error))

        def on_close(ws):
            Log.warn("WS closed unexpectedly for exchange {}".format(self.id))
            Log.info("restarting WS for exchange {}".format(self.id))
            self.__track_balances()

        ws = WebSocketApp(
            "wss://api.bitfinex.com/ws/",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws.on_open = on_open
        ws.run_forever()
        time.sleep(10)
        ws.close()

    @property
    def fees(self):
        return self.__fees

    def add_order(self, pair, side, order_type, price, volume, maker=False):
        # Bitfinex v1 API expects "BTCUSD", v2 API expects "tBTCUSD":
        pair = self.__translate_to[pair][1:]
        payload = {
            "request": "/v1/order/new",
            "nonce": self.__bfxv1._nonce(),
            "symbol": pair,
            "amount": str(volume),
            "price": str(price),
            "exchange": "bitfinex",
            "side": "buy" if side == Direction.BUY else "sell",
            "type": self.__order_types[order_type],
            "is_postonly": maker,
        }
        new_order = self.__bfxv1._post("/order/new", payload=payload, verify=True)
        order = Order(new_order["id"], self.id, pair, side, order_type, price, volume)
        if new_order["is_live"] == False:
            order.update_status(Order.Status.REJECTED)
        elif new_order["is_cancelled"] == False:
            order.update_status(Order.Status.CANCELLED)
        return order

    def cancel_order(self, order_id):
        return self.__bfxv1.delete_order(order_id)

    def order_status(self, order_id):
        return self.__bfxv1.status_order(order_id)

    def get_open_positions(self):
        return self.__bfxv1.active_orders()
