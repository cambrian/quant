from collections import defaultdict
from queue import Queue
from threading import Lock

import numpy as np
import pandas as pd

from trader.util import Feed
from trader.util.constants import BITFINEX, BTC, DUMMY, USD
from trader.util.log import Log
from trader.util.stats import Gaussian
from trader.util.types import Direction, Order, ExchangePair, TradingPair


class Executor:
    """Given fair updates, listens to book updates and places orders to optimize our portfolio.

    NOTE: We lock `__trade` by exchange/pair such that calls to it are skipped if a lock cannot
    be acquired. However, this only applies to order ticks (new fairs prices should always run a
    cycle of orders).

    Args:
        thread_manager (ThreadManager): A thread manager to attach any child threads for this
            executor object.
        exchange_pairs (dict): A dictionary indexed by exchange, consisting of the pairs from
            that exchange to execute on.

    """

    def __init__(self, thread_manager, exchange_pairs, size, min_edge):
        self.__books_lock = Lock()
        self.__trade_lock = Lock()
        self.__latest_books = {}  # keyed by (Exchange.id, pair)
        self.__latest_fairs = None
        self.__thread_manager = thread_manager
        self.__size = size
        self.__min_edge = min_edge
        self.__exchange_pairs = [
            ExchangePair(e.id, p) for e, ps in exchange_pairs.items() for p in ps
        ]
        self.__exchanges = {e.id: e for e in exchange_pairs}

        # Set up book feeds for every pair.
        for exchange_pair in self.__exchange_pairs:
            thread_manager.attach(
                "executor-{}".format(exchange_pair),
                self.__exchanges[exchange_pair.exchange_id]
                .book_feed(exchange_pair.pair)
                .subscribe(
                    # Ugly but otherwise the values of exchange/pair will get overwritten in
                    # the closure at every iteration...
                    lambda book, exchange_pair=exchange_pair: self.__tick_book(exchange_pair, book)
                ),
            )

    def __tick_book(self, exchange_pair, book):
        self.__books_lock.acquire()
        if exchange_pair in self.__latest_books:
            latest_book = self.__latest_books[exchange_pair]
            # Two order books can have the same bid/ask but different last trade price.
            if latest_book.bid == book.bid and latest_book.ask == book.ask:
                self.__books_lock.release()
                return
        self.__latest_books[exchange_pair] = book
        self.__books_lock.release()
        if exchange_pair.exchange_id != DUMMY and exchange_pair.exchange_id != BITFINEX:
            self.__trade()
        Log.data("executor-book", book)

    def __trade(self, wait_for_other_trade=False):
        """
        If `wait_for_other_trade` is false, doesn't try to trade if there is another thread
        attempting to trade. If true, it will wait for the other thread to finish and try
        immediately after.
        TODO: requires that __latest_fairs and self.__exchange_pairs have the same indexing. Make
        this explicit or don't require it.
        """
        if self.__latest_fairs is None:
            return

        if wait_for_other_trade:
            self.__trade_lock.acquire()
        elif not self.__trade_lock.acquire(blocking=False):
            return

        self.__books_lock.acquire()
        bids = pd.Series(index=self.__latest_fairs.mean.index)
        asks = pd.Series(index=self.__latest_fairs.mean.index)
        fees = pd.Series(index=self.__latest_fairs.mean.index)
        balances = {}
        for exchange_pair in self.__latest_fairs.mean.index:
            exchange = self.__exchanges[exchange_pair.exchange_id]
            book = self.__latest_books[exchange_pair]
            bids[exchange_pair] = book.bid
            asks[exchange_pair] = book.ask
            fees[exchange_pair] = exchange.fees["taker"]
            balances[exchange.id, exchange_pair.base] = exchange.balances[exchange_pair.base] or 0
        self.__books_lock.release()
        balances = pd.Series(balances)

        orders = self.get_orders(
            balances, bids, asks, self.__latest_fairs, self.__size, fees, self.__min_edge
        )
        Log.info("executor_orders {}".format(orders))

        for exchange_pair, order_size in orders.items():
            exchange = self.__exchanges[exchange_pair.exchange_id]
            if order_size < 0:
                order_size = abs(order_size)
                # if order_size > exchange.balances[exchange_pair.base]:
                #     order_size = exchange.balances[exchange_pair.base]
                if order_size > 0:
                    Log.data(
                        "executor-sell", {"pair": exchange_pair.json_value(), "size": order_size}
                    )
                    exchange.add_order(
                        exchange_pair.pair,
                        Direction.SELL,
                        Order.Type.IOC,
                        bids[exchange_pair],
                        order_size,
                    )
            elif order_size > 0:
                # if order_size * asks[exchange_pair] > exchange.balances[exchange_pair.quote]:
                #     order_size = exchange.balances[exchange_pair.quote] / asks[exchange_pair]
                if order_size > 0:
                    Log.data(
                        "executor-buy", {"pair": exchange_pair.json_value(), "size": order_size}
                    )
                    exchange.add_order(
                        exchange_pair.pair,
                        Direction.BUY,
                        Order.Type.IOC,
                        asks[exchange_pair],
                        order_size,
                    )
        self.__trade_lock.release()

    def tick_fairs(self, fairs):
        self.__latest_fairs = fairs
        self.__thread_manager.attach(
            "executor-fairs", lambda: self.__trade(wait_for_other_trade=True), should_terminate=True
        )

    def order_size(self, direction, fees, balance, fair, price):
        dir_ = 1 if direction == Direction.BUY else -1
        edge = ((fair.mean / price - 1) * dir_ - fees) / fair.stddev
        # Positive edge --> profitable order.
        desired_balance_value = edge * self.__size * dir_
        proposed_order_size = (desired_balance_value / price - balance) * dir_
        return max(0, proposed_order_size)

    def get_orders(self, balances, bids, asks, fairs, size, fees, min_edge):
        """Takes fair as Gaussian, balances in base currency.
        Returns orders in base currency (negative size indicates sell).

        Since our fair estimate may have skewed uncertainty, it may be the case that
        a price change for one trading pair causes us to desire positions in other
        pairs. Therefore get_orders needs to consider the entire set of fairs and
        bid/asks at once.
        """
        mids = (bids + asks) / 2  # Use mid price for target balance value calculations.
        quote_currency = mids.index[0].quote

        gradient = fairs.gradient(mids) * fairs.mean
        balance_direction_vector = gradient / (np.linalg.norm(gradient) + 1e-100)
        target_balance_values = balance_direction_vector * fairs.z_score(mids) * size
        pair_balances = balances.set_axis(
            [ExchangePair(e, TradingPair(b, quote_currency)) for e, b in balances.index],
            inplace=False,
        )[mids.index]
        proposed_orders = target_balance_values / fairs.mean - pair_balances
        prices = (proposed_orders >= 0) * asks + (proposed_orders < 0) * bids
        profitable = np.sign(proposed_orders) * (fairs.mean / prices - 1) > fees + min_edge
        profitable_orders = proposed_orders * profitable
        Log.data("balances", str(pair_balances))
        Log.data("fairs", str(fairs.mean))
        Log.data("mids", str(mids))
        Log.data("proposed_orders", str(proposed_orders))
        return profitable_orders
