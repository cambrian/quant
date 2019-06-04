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
from trader.util.constants import not_implemented
from trader.util.types import BookLevel, Direction, ExchangePair, Order, OrderBook


def dummy_exchanges(thread_manager, data):
    exchange_ids = {ep.exchange_id for ep in data.iloc[0].index}
    return [DummyExchange(thread_manager, e, data) for e in exchange_ids]


class DummyExchange(Exchange):
    """
    Dummy exchange to simulate a single base exchange. Uses historical data and executes orders at
    last trade price.
    data may contain pairs for other base exchanges but they will be ignored.
    """

    def __init__(
        self, thread_manager, base_exchange_id, data, fees={"maker": 0.001, "taker": 0.002}
    ):
        super().__init__(thread_manager)
        self.__data = data
        self.__base_exchange_id = base_exchange_id
        self.__supported_pairs = [ep.pair for ep in data.iloc[0].index]
        # `time` is not private to allow manual adjustment.
        self.time = 0
        self.__fees = fees
        self.__book_queues = {pair: Queue() for pair in self.__supported_pairs}
        self.__book_feeds = {}
        self.__latest_books = {}
        self.__balances = defaultdict(float)
        self.__order_id = 0

    @property
    def base_exchange_id(self):
        return self.__base_exchange_id

    @property
    def id(self):
        return self.__base_exchange_id + "(dummy)"

    def step_time(self):
        """Returns False if all data has been exhausted."""
        if self.time >= len(self.__data.index):
            return False
        frame = self.__data.iloc[self.time]
        for ep, (price, _) in frame.iterrows():
            if ep.exchange_id != self.base_exchange_id:
                continue
            ep = ExchangePair(self.id, ep.pair)
            dummy_book = OrderBook(ep, [BookLevel(price, 1)], [BookLevel(price, 1)])
            self.__book_queues[ep.pair].put(dummy_book)
            self.__latest_books[ep.pair] = dummy_book
        Log.info("dummy-step", self.time)
        self.time += 1
        return True

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

    def frame(self, pairs):
        eps = [ExchangePair(self.base_exchange_id, pair) for pair in pairs]
        frame = self.__data.iloc[self.time].loc[eps]
        return frame.set_axis([ExchangePair(self.id, pair) for pair in pairs], inplace=False)

    # TODO
    def balances_feed(self):
        pass

    @property
    def balances(self):
        return self.__balances

    @property
    def fees(self):
        return self.__fees

    def add_order(self, pair, side, order_type, price, size, maker=False):
        if side == Direction.BUY:
            # if pair not in self.__latest_books or price != self.__latest_books[pair].ask:
            #     Log.info("dummy-buy - order not filled because price is not most recent.")
            #     return None
            self.__balances[pair.base] += size
            self.__balances[pair.quote] -= size * price
        else:
            # if pair not in self.__latest_books or price != self.__latest_books[pair].bid:
            #     Log.info("dummy-sell - order not filled because price is not most recent.")
            #     return None
            self.__balances[pair.base] -= size
            self.__balances[pair.quote] += size * price
        order = Order(self.__order_id, self.id, pair, side, order_type, price, size)
        Log.info("dummy order", order)
        self.__order_id += 1
        Log.info("dummy balances", self.__balances)
        return order

    # Unnecessary since orders are immediate.
    def cancel_order(self, order_id):
        not_implemented()

    # Unnecessary since orders are immediate.
    def get_open_positions(self):
        not_implemented()
