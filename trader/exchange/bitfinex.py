import hashlib
import hmac
import json
import os
import time
from collections import defaultdict
from copy import deepcopy
from queue import Queue

import numpy as np
import pandas as pd
from bitfinex import ClientV1, ClientV2, WssClient
from sortedcontainers import SortedList
from websocket import WebSocketApp

from trader.exchange.base import Exchange, ExchangeError
from trader.util import Feed, Log
from trader.util.constants import (BITFINEX, BTC, BTC_USD, ETH, ETH_USD, USD,
                                   XRP, XRP_USD)
from trader.util.thread import MVar
from trader.util.types import (BookLevel, Direction, ExchangePair, Order,
                               OrderBook, Side)


class Bitfinex(Exchange):
    """The Bitfinex exchange.

    Store your API key and secret in the `BITFINEX_API_KEY` and `BITFINEX_SECRET` environment
    variables.

    """

    # Allow only 1 instance. In the near future we should change the exchange classes to actually
    # be singletons, but first we should extract common logic into the `Exchange` base class before
    # making that change.
    __instance_exists = False

    def __init__(self, thread_manager, pairs):
        assert not Bitfinex.__instance_exists
        Bitfinex.__instance_exists = True
        super().__init__(thread_manager)
        self.__api_key = os.getenv("BITFINEX_API_KEY", "")
        self.__api_secret = os.getenv("BITFINEX_SECRET", "")
        self.__bfxv1 = ClientV1(self.__api_key, self.__api_secret, 2.0)
        self.__bfxv2 = ClientV2(self.__api_key, self.__api_secret)
        self.__ws_client = WssClient(self.__api_key, self.__api_secret)
        self.__ws_client.authenticate(lambda x: None)
        self.__ws_client.daemon = True
        # TODO: these should probably be functions
        self.__translate_to = {BTC_USD: "tBTCUSD", ETH_USD: "tETHUSD", XRP_USD: "tXRPUSD"}
        self.__translate_from = {"USD": USD, "BTC": BTC, "ETH": ETH, "XRP": XRP}
        self.__pairs = pairs
        self.__order_types = {
            Order.Type.MARKET: "exchange market",
            Order.Type.LIMIT: "exchange limit",
            Order.Type.IOC: "exchange immediate-or-cancel",
            Order.Type.FOK: "exchange fill-or-kill",
        }
        self.__book_feeds = {}
        self.__trade_feeds = {}
        self.__balances_queue = Queue()
        self.__balances_feed = None
        thread_manager.attach("bitfinex-balances-queue", self.__track_balances)
        # TODO: Can this be dynamically loaded? (For other exchanges too.)
        self.__fees = {"maker": 0.001, "taker": 0.002}
        # TODO: Maybe start this in a lazy way?
        self.__ws_client.start()
        self.__frame = pd.DataFrame(
            0.0,
            index=list(map(lambda x: ExchangePair(self.id, x), pairs)),
            columns=["price", "volume"],
        )

        for pair in pairs:
            pair_feed_book, runner_book = Feed.of(self.__generate_book_feed(pair))
            self._thread_manager.attach("bitfinex-{}-book".format(pair), runner_book)
            self.__book_feeds[pair] = pair_feed_book
            pair_feed_trade, runner_trade = Feed.of(self.__generate_trade_feed(pair))
            self._thread_manager.attach("bitfinex-{}-trade".format(pair), runner_trade)
            self.__trade_feeds[pair] = pair_feed_trade

    @property
    def id(self):
        return BITFINEX

    def book_feed(self, pair):
        if pair not in self.__pairs:
            raise ExchangeError("pair not supported by Bitfinex")
        return self.__book_feeds[pair]

    def __generate_book_feed(self, pair):
        msg_queue = Queue()

        def add_messages_to_queue(message):
            # Ignore status/subscription dicts.
            if isinstance(message, list):
                msg_queue.put(message)

        self.__ws_client.subscribe_to_orderbook(
            self.__translate_to[pair], precision="P0", callback=add_messages_to_queue
        )

        order_book = OrderBook(ExchangePair(self.id, pair))

        def handle_update(order_book, update):
            if update != "hb":
                side = Side.BID if update[2] > 0 else Side.ASK
                size = abs(update[2]) if update[1] != 0 else 0
                order_book.update(side, BookLevel(update[0], size))

        while True:
            msg = msg_queue.get()
            # see https://docs.bitfinex.com/v2/reference#ws-public-order-books for spec.
            if len(msg) == 2 and isinstance(msg[1][0], list):
                order_book.clear()
                for update in msg[1]:
                    handle_update(order_book, update)
            else:
                handle_update(order_book, msg[1])
            yield order_book

    def __generate_trade_feed(self, pair):
        msg_queue = Queue()

        def add_messages_to_queue(message):
            msg_queue.put(message)

        self.__ws_client.subscribe_to_trades(
            self.__translate_to[pair], callback=add_messages_to_queue
        )

        while True:
            msg = msg_queue.get()
            # First two check if msg is a 'te' or 'tu' message
            # see https://docs.bitfinex.com/v2/reference for spec.
            if isinstance(msg, list) and len(msg) == 3 and msg[1] == "te":
                # We only track 'te' trade executions
                self.__frame.loc[ExchangePair(self.id, pair), "price"] = float(msg[2][3])
                self.__frame.loc[ExchangePair(self.id, pair), "volume"] += abs(float(msg[2][2]))

            yield self.__frame

    # TODO: return only pairs? If this is a feature we want
    def frame(self, _pairs):
        """
        Returns frame for tracked pairs.
        """
        frame = self.__frame.copy()
        self.__frame["volume"] = 0
        return frame

    def balances_feed(self):
        if self.__balances_feed is None:
            balances_feed, runner = Feed.of(iter(self.__balances_queue.get, None))
            self._thread_manager.attach("bitfinex-balances-feed", runner)
            self.__balances_feed = balances_feed
        return self.__balances_feed

    def __track_balances(self):
        """Thread function to constantly track exchange's balance."""
        balances = defaultdict(float)

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
                    balances[self.__translate_from[update[1]]] = update[2]
                    self.__balances_queue.put(deepcopy(balances))

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
    def balances(self):
        if self.__balances_feed is None:
            return self.balances_feed().latest
        return self.__balances_feed.latest

    @property
    def fees(self):
        return self.__fees

    # Note: could be more efficient but this function isn't very important
    def get_warmup_data(self, pairs, duration, resolution):
        rows = 0
        data = {}

        # Collect data from bitfinex API
        while rows < duration:
            for pair in pairs:
                trans_pair = self.__translate_to[pair]
                if rows == 0:
                    data[pair] = self.__bfxv2.candles(resolution, trans_pair, "hist", limit="5000")
                else:
                    data[pair] = list(
                        np.concatenate(
                            (
                                data[pair],
                                self.__bfxv2.candles(
                                    resolution, trans_pair, "hist", limit="5000", end=last_time
                                )[1:],
                            ),
                            axis=0,
                        )
                    )
            last_time = data[pairs[0]][-1][0]
            rows += len(data[pairs[0]])

        # Prune data to only # duration elements
        for row in data:
            data[row] = data[row][:duration]

        # Prep data for strategy consumption
        prepped = []
        for i in range(0, len(data[pairs[0]])):
            tick_data = {}
            for pair in pairs:
                elem = data[pair][i]
                tick_data[ExchangePair(self.id, pair)] = (elem[1], elem[4])
            tick_data = pd.DataFrame.from_dict(
                tick_data, orient="index", columns=["price", "volume"]
            )
            prepped.append(tick_data)
        return prepped

    # TODO: use order type in argument
    def add_order(self, pair, side, order_type, price, size, maker=False):
        # Bitfinex v1 API expects "BTCUSD", v2 API expects "tBTCUSD":
        pair = self.__translate_to[pair][1:]
        payload = {
            "request": "/v1/order/new",
            "nonce": self.__bfxv1._nonce(),
            "symbol": pair,
            "amount": str(size),
            "price": str(price),
            "exchange": "bitfinex",
            "side": "buy" if side == Direction.BUY else "sell",
            "type": self.__order_types[order_type],
            "is_postonly": maker,
        }
        new_order = self.__bfxv1._post("/order/new", payload=payload, verify=True)
        Log.info("Bitfinex-order", new_order)
        if "id" in new_order:
            order = Order(new_order["id"], self.id, pair, side, order_type, price, size)
            if new_order["is_live"] == False:
                order.update_status(Order.Status.REJECTED)
            elif new_order["is_cancelled"] == False:
                order.update_status(Order.Status.CANCELLED)
            return order
        return None

    def cancel_order(self, order_id):
        return self.__bfxv1.delete_order(order_id)

    def order_status(self, order_id):
        return self.__bfxv1.status_order(order_id)

    def get_open_positions(self):
        return self.__bfxv1.active_orders()
