import hashlib
import hmac
import json
import os
import random
import time
from collections import defaultdict
from queue import Queue

import pandas as pd
from bitfinex import ClientV1, ClientV2, WssClient
from sortedcontainers import SortedList
from websocket import create_connection

from trader.exchange.base import Exchange, ExchangeError
from trader.util import Feed, Log
from trader.util.constants import (BTC, BTC_USDT, DUMMY, ETH, ETH_USDT,
                                   LTC_USDT, USD, USDT, XRP, XRP_USDT,
                                   not_implemented)
from trader.util.types import (Direction, ExchangePair, Order, OrderBook)


# TODO (remove this when the Exchange interface is stable and changes are complete)
class DummyExchange(Exchange):
    """Dummy exchange. Uses historical data and executes orders at last trade price."""

    # Allow only 1 instance. In the near future we should change the exchange classes to actually
    # be singletons, but first we should extract common logic into the `Exchange` base class before
    # making that change.
    __instance_exists = False

    def __init__(self, thread_manager, data, fees):
        assert not DummyExchange.__instance_exists
        DummyExchange.__instance_exists = True
        super().__init__(thread_manager)
        self.__data = data
        self.__supported_pairs = data.iloc[0].index
        # `time` is not private to allow manual adjustment.
        self.time = 0
        self.__fees = {"maker": 0.001, "taker": 0.002}
        self.__book_queues = {pair: Queue() for pair in self.__supported_pairs}
        self.__books = {}
        self.__latest_books = {}
        self.__prices = {pair: (0, 0) for pair in self.__supported_pairs}
        self.__balances = defaultdict(float)
        self.__balances[BTC] = 2.43478623
        self.__balances[USDT] = 245.17003318
        self.translate = {
            'BTC-USDT': "BTC_USDT",
            'ETH-USDT': "ETH_USDT",
            'XRP-USDT': "XRP_USDT",
            'LTC-USDT': "LTC_USDT",
        }
        self.__order_id = 0

    @property
    def id(self):
        return DUMMY

    def step_time(self):
        data = self.__data.iloc[self.time]
        data_list = list(data.items())
        prices = list(data_list[0][1].items())
        volumes = list(data_list[1][1].items())
        pair_data = list(map(lambda x: (x[0][1], x[1][1]), list(zip(prices, volumes))))
        for i, pair in enumerate(self.__supported_pairs):
            self.__book_queues[pair].put(pair_data[i])
            self.__prices[pair] = pair_data[i]
        Log.data("dummy-debug", {"step": self.time, "prices": self.__prices})
        self.time += 1

    def book_feed(self, pair):
        trans_pair = self.translate[pair]
        if trans_pair not in self.__supported_pairs:
            raise ExchangeError("pair not supported by " + self.id)
        if trans_pair in self.__books:
            return self.__books[trans_pair]
        else:
            pair_feed, runner = Feed.of(self.__book(pair))
            self._thread_manager.attach("dummy-{}-book".format(pair), runner)
            self.__books[trans_pair] = pair_feed
            return pair_feed

    def __book(self, pair):
        while True:
            trans_pair = self.translate[pair]
            (price, _) = self.__book_queues[trans_pair].get()
            # Spread is hard to manage generally across currencies
            spread = 0  # random.random()
            book = OrderBook(ExchangePair(self.id, pair), price, price - spread, price + spread)
            self.__latest_books[pair] = book
            yield book

    def prices(self, pairs, time_frame=None):
        """

        NOTE: `time_frame` expected as Bitfinex-specific string representation (e.g. '1m').

        """
        data = {}
        for pair in pairs:
            trans_pair = self.translate[repr(pair)]
            if trans_pair not in self.__supported_pairs:
                raise ExchangeError("pair not supported by Dummy")
            if trans_pair in self.__prices:
                val = self.__prices[trans_pair]
            else:
                # Prices should be tracked in `step_time`.
                val = (0, 0)
            data[ExchangePair(self.id, pair)] = val
        Log.info("Dummy-prices {}".format(data))
        # Log.data("Dummy-prices", {"data": data})
        return pd.DataFrame.from_dict(data, orient="index", columns=["price", "volume"])

    # TODO
    def balances_feed(self):
        pass

    @property
    def balances(self):
        return self.__balances

    @property
    def fees(self):
        return self.__fees

    def add_order(self, pair, side, order_type, price, volume, maker=False):
        if side == Direction.BUY:
            # if pair not in self.__latest_books or price != self.__latest_books[pair].ask:
            #     Log.info("dummy-buy - order not filled because price is not most recent.")
            #     return None
            Log.data("dummy-buy", {"size": volume, "pair": pair.json_value(), "price": price})
            self.__balances[pair.base] += volume
            self.__balances[pair.quote] -= volume * price
        else:
            # if pair not in self.__latest_books or price != self.__latest_books[pair].bid:
            #     Log.info("dummy-sell - order not filled because price is not most recent.")
            #     return None
            Log.data("dummy-sell", {"size": volume, "pair": pair.json_value(), "price": price})
            self.__balances[pair.base] -= volume
            self.__balances[pair.quote] += volume * price
        order = Order(self.__order_id, self.id, pair, side, order_type, price, volume)
        self.__order_id += 1
        Log.info("dummy-balances {}".format(self.__balances))
        return order

    # Unnecessary since orders are immediate.
    def cancel_order(self, order_id):
        not_implemented()

    # Unnecessary since orders are immediate.
    def get_open_positions(self):
        not_implemented()
