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
from trader.util.constants import (
    BTC,
    BTC_USDT,
    DUMMY,
    ETH,
    ETH_USDT,
    LTC_USDT,
    USD,
    USDT,
    XRP,
    XRP_USDT,
    not_implemented,
)
from trader.util.types import BookLevel, Direction, ExchangePair, Order, OrderBook


def dummy_exchanges(data):
    pass


class DummyExchange(Exchange):
    """Dummy exchange. Uses historical data and executes orders at last trade price."""

    def __init__(self, thread_manager, data, fees={"maker": 0.001, "taker": 0.002}):
        super().__init__(thread_manager)
        self.__data = data
        self.__supported_pairs = data.iloc[0].index
        # `time` is not private to allow manual adjustment.
        self.time = 0
        self.__fees = fees
        self.__book_queues = {pair: Queue() for pair in self.__supported_pairs}
        self.__book_feeds = {}
        self.__latest_books = {}
        self.__balances = defaultdict(float)
        self.__balances[BTC] = 2.43478623
        self.__balances[USDT] = 245.17003318
        self.__order_id = 0

    @property
    def id(self):
        return DUMMY

    def step_time(self):
        frame = self.__data.iloc[self.time]
        for pair, (price, _) in frame.items():
            dummy_book = OrderBook(pair, [BookLevel(price, 1)], [BookLevel(price, 1)])
            self.__book_queues[pair].put(dummy_book)
            self.__latest_books[pair] = dummy_book
        Log.data("dummy-debug", {"step": self.time, "frame": frame})
        self.time += 1

    def book_feed(self, pair):
        if pair not in self.__supported_pairs:
            raise ExchangeError("pair not supported by " + self.id)
        if pair in self.__book_feeds:
            return self.__book_feeds[pair]
        else:
            pair_feed, runner = Feed.of(self.__book_generator(pair))
            self._thread_manager.attach("dummy-{}-book".format(pair), runner)
            self.__book_feeds[pair] = pair_feed
            return pair_feed

    def __book_generator(self, pair):
        while True:
            book = self.__book_queues[pair].get()
            yield book

    def prices(self, pairs, time_frame=None):
        """

        NOTE: `time_frame` expected as Bitfinex-specific string representation (e.g. '1m').

        """
        return self.__data.iloc[self.time].loc[pairs]

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
