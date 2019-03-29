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
from websocket import create_connection

from trader.exchange.base import Exchange, ExchangeError
from trader.util.constants import (BTC, BTC_USD, ETH, ETH_USD, USD, XRP,
                                   XRP_USD, not_implemented)
from trader.util.feed import Feed
from trader.util.types import OrderBook


class DummyExchange(Exchange):
    """Dummy exchange. Uses historical data and executes orders at last trade price.
    """

    # Allow only 1 instance. In the near future we should change the exchange classes to actually
    # be singletons, but first we should extract common logic into the Exchange base class before
    # making that change.
    __instance_exists = False

    def __init__(self, thread_manager, data):
        assert not DummyExchange.__instance_exists
        DummyExchange.__instance_exists = True
        super().__init__(thread_manager)
        self.__data = data
        self.__supported_pairs = data.columns  # or similar
        self.time = 0  # allow manual setting
        # TODO:
        self.__fees = {"maker": 0.001, "taker": 0.002}
        self.__books = {}
        self.__prices = {}
        self.__balances = defaultdict(float)

    @property
    def id(self):
        return "DUMMY_EXCHANGE"

    def step_time(self):
        self.time += 1
        # TODO: also stream next book, price

    def book(self, pair):
        if pair not in self.__supported_pairs:
            raise ExchangeError("pair not supported by " + self.id)
        price = data.loc[time]
        book = OrderBook(self.id, pair, last_price=price, bid=price, ask=price)
        # TODO:
        not_implemented()

    def prices(self, pairs, time_frame):
        """

        NOTE: `time_frame` expected as Bitfinex-specific string representation (e.g. '1m').

        """
        not_implemented()

    @property
    def balances(self):
        return self.__balances

    def __track_balances(self):
        not_implemented()

    @property
    def fees(self):
        return self.__fees

    def add_order(self, pair, side, order_type, price, volume, maker=False):
        # TODO: Formalize nicer way - v1 API expects "BTCUSD", v2 API expects "tBTCUSD"
        # Strip "t"

        not_implemented()

    def cancel_order(self, order_id):
        not_implemented()

    def get_open_positions(self):
        not_implemented()
