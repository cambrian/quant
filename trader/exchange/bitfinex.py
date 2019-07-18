import hashlib
import hmac
import json
import time
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from queue import Queue

import numpy as np
import pandas as pd
from bitfinex import ClientV1, ClientV2, WssClient
from websocket import WebSocketApp

from trader.exchange.base import Exchange, ExchangeError
from trader.util import Feed, Log
from trader.util.constants import BITFINEX, BTC, BTC_USD, ETH, ETH_USD, USD, XRP, XRP_USD
from trader.util.types import (
    BookLevel,
    Currency,
    ExchangePair,
    OpenOrder,
    Order,
    OrderBook,
    Side,
    TradingPair,
)


class Bitfinex(Exchange):
    """The Bitfinex exchange.

    Store your API key and secret in the `BITFINEX_API_KEY` and `BITFINEX_SECRET` environment
    variables.

    """

    # Allow only 1 instance. In the near future we should change the exchange classes to actually
    # be singletons, but first we should extract common logic into the `Exchange` base class before
    # making that change.
    __instance_exists = False

    def __init__(self, thread_manager, keys, pairs):
        """
        keys as parsed from keys/bitfinex.json
        """
        assert not Bitfinex.__instance_exists
        Bitfinex.__instance_exists = True
        super().__init__(thread_manager)
        self.__api_key = keys["key"]
        self.__api_secret = keys["secret"]
        self.__bfxv1 = ClientV1(self.__api_key, self.__api_secret, 2.0)
        self.__bfxv2 = ClientV2(self.__api_key, self.__api_secret)
        self.__ws_client = WssClient(self.__api_key, self.__api_secret)
        self.__ws_client.authenticate(lambda x: None)
        self.__ws_client.daemon = True
        self.__pairs = pairs
        self.__order_types = {
            Order.Type.MARKET: "market",
            Order.Type.LIMIT: "limit",
            Order.Type.IOC: "immediate-or-cancel",
            Order.Type.FOK: "fill-or-kill",
        }
        self.__book_feeds = {}
        self.__trade_feeds = {}
        self.__positions_queue = Queue()
        self.__positions_feed = self.positions_feed()
        thread_manager.attach("bitfinex-positions-queue", self.__track_positions)
        # TODO: Can this be dynamically loaded? (For other exchanges too.)
        self.__fees = {"maker": 0.001, "taker": 0.002}
        # TODO: Maybe start this in a lazy way?
        self.__ws_client.start()
        self.__frame = pd.Series(
            0.0,  # setting the initial value to 0 is important for volume tracking to work properly
            index=pd.MultiIndex.from_product(
                [[ExchangePair(self.id, x) for x in pairs], ["price", "volume"]]
            ),
        )

        for pair in pairs:
            pair_feed_book, runner_book = Feed.of(self.__generate_book_feed(pair))
            self._thread_manager.attach(f"bitfinex-{pair}-book", runner_book)
            self.__book_feeds[pair] = pair_feed_book
            pair_feed_trade, runner_trade = Feed.of(self.__generate_trade_feed(pair))
            self._thread_manager.attach(f"bitfinex-{pair}-trade", runner_trade)
            self.__trade_feeds[pair] = pair_feed_trade

    @property
    def id(self):
        return BITFINEX

    @staticmethod
    def encode_trading_pair(pair):
        base = pair.base if pair.base != Currency("BCH") else Currency("BAB")
        return f"t{base}{pair.quote}"

    @staticmethod
    def decode_trading_pair(pair_string):
        base_string = pair_string[1:4] if pair_string[1:4] != "BAB" else "BCH"
        return TradingPair(Currency(base_string), Currency(pair_string[4:7]))

    def book_feed(self, pair):
        if pair not in self.__pairs:
            raise ExchangeError("pair not supported by this Bitfinex client")
        return self.__book_feeds[pair]

    def __generate_book_feed(self, pair):
        msg_queue = Queue()

        self.__ws_client.subscribe_to_orderbook(
            Bitfinex.encode_trading_pair(pair), precision="P0", callback=msg_queue.put
        )

        order_book = OrderBook(ExchangePair(self.id, pair))

        def handle_update(order_book, update):
            side = Side.BUY if update[2] > 0 else Side.SELL
            size = abs(update[2]) if update[1] != 0 else 0
            order_book.update(side, BookLevel(update[0], size))

        while True:
            msg = msg_queue.get()
            # Ignore status/subscription dicts, heartbeats
            if not isinstance(msg, list) or msg[1] == "hb":
                continue
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

        self.__ws_client.subscribe_to_trades(
            Bitfinex.encode_trading_pair(pair), callback=msg_queue.put
        )

        while True:
            msg = msg_queue.get()
            # We only track 'te' trade executions (ignoring "tu" trade updates)
            # see https://docs.bitfinex.com/v2/reference for spec.
            if not isinstance(msg, list) or msg[1] != "te":
                continue
            self.__frame.loc[ExchangePair(self.id, pair), "price"] = float(msg[2][3])
            self.__frame.loc[ExchangePair(self.id, pair), "volume"] += abs(float(msg[2][2]))

            yield self.__frame

    def frame(self, pairs):
        """
        Returns frame for requested pairs.
        """
        frame = self.__frame.copy()
        self.__frame.loc[pd.IndexSlice[[ExchangePair(self.id, p) for p in pairs], "volume"]] = 0
        return frame

    def positions_feed(self):
        if not hasattr(self, "__positions_feed") or self.__positions_feed is None:
            positions_feed, runner = Feed.of(iter(self.__positions_queue.get, None))
            self._thread_manager.attach("bitfinex-positions-feed", runner)
            self.__positions_feed = positions_feed
        return self.__positions_feed

    def __track_positions(self):
        if not hasattr(self, "__positions_feed") or self.__positions_feed is None:
            positions = defaultdict(float)
            for pair in self.__pairs:
                currency = pair.base
                positions[currency] = 0.0
            self.__positions_queue.put(deepcopy(positions))

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
                "filter": ["trading"],
            }
            ws.send(json.dumps(payload))

        def on_message(ws, msg):
            msg = json.loads(msg)

            # Ignore heartbeats or other irrelevant msgs
            if not isinstance(msg, list) or len(msg) <= 1 or msg[1] == "hb":
                return

            def update_positions(update, value=None):
                currency = Bitfinex.decode_trading_pair(update[0]).base
                # Only track exchange (trading) wallet.
                if len(update) >= 6:
                    # If position is inactive, zero out balance
                    if update[1] != "ACTIVE":
                        value = 0.0
                    if value is None:
                        positions[currency] = float(update[2])
                    else:
                        positions[currency] = value
                self.__positions_queue.put(deepcopy(positions))

            # Disambiguate positions snapshot/update/new/closed:
            if msg[1] == "ps":
                for update in msg[2]:
                    update_positions(update)
            elif msg[1] == "pn" or msg[1] == "pu":
                update_positions(msg[2])
            elif msg[1] == "pc":
                update_positions(msg[2], 0.0)

        # TODO: should probably abort
        def on_error(ws, error):
            Log.warn("WS error within __track_positions for exchange {}: {}".format(self.id, error))

        # TODO: refactor to not be recursive (bc of stack growth)
        def on_close(ws):
            Log.warn("WS closed unexpectedly for exchange {}".format(self.id))
            Log.info("restarting WS for exchange {}".format(self.id))
            time.sleep(3)
            self.__track_positions()

        ws = WebSocketApp(
            "wss://api.bitfinex.com/ws/",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws.on_open = on_open
        ws.run_forever()

    @property
    def positions(self):
        if self.__positions_feed is None:
            return self.positions_feed().latest
        return self.__positions_feed.latest

    @property
    def fees(self):
        return self.__fees

    def get_warmup_data(self, pairs, duration, resolution):
        rows = 0
        data = {}
        last_time = None

        # Collect data from bitfinex API
        while rows < duration:
            for pair in pairs:
                bfx_pair = Bitfinex.encode_trading_pair(pair)
                limit = min(duration - rows, 5000)
                if last_time is None:
                    data[pair] = self.__bfxv2.candles(resolution, bfx_pair, "hist", limit=limit)
                else:
                    limit = min(limit + 1, 5000)
                    data[pair] += self.__bfxv2.candles(
                        resolution, bfx_pair, "hist", limit=limit, end=last_time
                    )[1:]
            last_time = data[pairs[0]][-1][0]
            rows = len(data[pairs[0]])

        # Prep data for strategy consumption
        prepped = []
        times = []
        for i in range(0, len(data[pairs[0]])):
            frame = {}
            for pair in pairs:
                elem = data[pair][i]
                frame[ExchangePair(self.id, pair), "price"] = elem[2]
                frame[ExchangePair(self.id, pair), "volume"] = elem[5]
            prepped.append(pd.Series(frame))
            times.append(datetime.fromtimestamp(data[pairs[0]][i][0] / 1000))
        prepped = pd.DataFrame(prepped, index=times).iloc[::-1]

        # TODO: also set last trade prices?
        return prepped

    def add_order(self, order):
        assert order.exchange_id == self.id
        payload = {
            "request": "/v1/order/new",
            "nonce": self.__bfxv1._nonce(),
            # Bitfinex v1 API expects "BTCUSD", v2 API expects "tBTCUSD":
            "symbol": Bitfinex.encode_trading_pair(order.pair)[1:],
            "amount": str(order.size),
            "price": str(order.price),
            "exchange": "bitfinex",
            "side": order.side.name.lower(),
            "type": self.__order_types[order.order_type],
            "is_postonly": order.maker_only,
        }
        try:
            response = self.__bfxv1._post("/order/new", payload=payload, verify=True)
        except TypeError as err:
            Log.warn("Bitfinex _post type error: {}".format(err))
        except Exception as err:
            Log.warn("Swallowing unexpected error: {}".format(err))
            return None
        # TODO: don't ignore error responses
        Log.debug("Bitfinex-order-response", response)
        if "id" in response:
            order = OpenOrder(order, response["id"])
            if not response["is_live"]:
                order.update_status(Order.Status.REJECTED)
            elif not response["is_cancelled"]:
                order.update_status(Order.Status.CANCELLED)
            return order
        return None

    def cancel_order(self, order_id):
        return self.__bfxv1.delete_order(order_id)

    def order_status(self, order_id):
        return self.__bfxv1.status_order(order_id)

    def get_open_positions(self):
        return self.__bfxv1.active_orders()
