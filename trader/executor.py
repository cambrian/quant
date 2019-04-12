from collections import defaultdict
from queue import Queue
from threading import Lock

import numpy as np
import pandas as pd

from trader.util import Feed
from trader.util.constants import TradingPair
from trader.util.log import Log
from trader.util.stats import Gaussian
from trader.util.types import Direction, Order

SIZE_PARAMETER = 100


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

    def __init__(self, thread_manager, exchange_pairs):
        self.__books_lock = Lock()
        self.__trade_locks = defaultdict(Lock)
        self.__latest_books = {}
        self.__latest_fairs = None
        self.__thread_manager = thread_manager

        # Set up book feeds for every pair.
        for exchange, pairs in exchange_pairs.items():
            for pair in pairs:
                thread_manager.attach(
                    "executor-{}-{}".format(exchange.id, pair),
                    exchange.book_feed(pair).subscribe(
                        # Ugly but otherwise the values of exchange/pair will get overwritten in
                        # the closure at every iteration...
                        lambda book, exchange=exchange, pair=pair: self.__tick_book(
                            exchange, pair, book
                        )
                    ),
                )

    def __tick_book(self, exchange, pair, book):
        self.__books_lock.acquire()
        if (exchange, pair) in self.__latest_books:
            latest_book = self.__latest_books[exchange, pair]
            # Two order books can have the same bid/ask but different last trade price.
            if latest_book.bid == book.bid and latest_book.ask == book.ask:
                self.__books_lock.release()
                return
        self.__latest_books[exchange, pair] = book
        self.__books_lock.release()
        self.__trade(exchange, pair)
        Log.data("executor-book", book)

    def __trade(self, exchange, pair, wait_for_other_trade=False):
        """
        If `wait_for_other_trade` is false, doesn't try to trade if there is another thread trading
        this same exchange pair. If true, it will wait for the other thread to finish trading this
        pair and try immediately after.
        """
        trade_lock = self.__trade_locks[exchange, pair]
        if wait_for_other_trade:
            trade_lock.acquire()
        elif not trade_lock.acquire(blocking=False):
            return

        self.__books_lock.acquire()
        book = self.__latest_books[exchange, pair]
        bids = {}
        asks = {}
        fees = {}
        for (exchange, pair) in self.__latest_books:
            book = self.__latest_books[exchange, pair]
            bids[pair] = book.bid
            asks[pair] = book.ask
            fees[pair] = exchange.fees["taker"]
            if pair.base not in exchange.balances:
                exchange.balances[pair.base] = 0.0
        self.__books_lock.release()
        bids = pd.Series(bids)
        asks = pd.Series(asks)
        fees = pd.Series(fees)

        if self.__latest_fairs is None:
            trade_lock.release()
            return

        ask = book.ask
        bid = book.bid
        balance = exchange.balances[pair.base]
        min_edge = 1
        # fees = exchange.fees

        orders = self.get_orders(
            exchange.balances, bids, asks, self.__latest_fairs, SIZE_PARAMETER, fees, min_edge
        )
        print(orders)

        # for (
        #     order_exchange_pair,
        #     order_size,
        # ) in orders.items():  # double check pandas iteration syntax
        #     print(order_exchange_pair, order_size)
        # exchange_name, pair = order_exchange_pair.split("_", 1)
        # if order_size < 0:
        #     fill = exchanges[exchange_name].order(pair=pair, direction=SELL, price=bid, size=sell_size, order_type=IMMEDIATE_OR_CANCEL)
        #     update_balances(balances, fill)
        # else if order_size > 0:
        #     fill = exchanges[exchange_name].order(pair=pair, direction=BUY, price=ask, size=buy_size, order_type=IMMEDIATE_OR_CANCEL)
        #     update_balances(balances, fill)
        trade_lock.release()

    def tick_fairs(self, fairs):
        self.__latest_fairs = fairs

        self.__books_lock.acquire()
        for exchange, pair in self.__latest_books:
            self.__thread_manager.attach(
                "executor-fairs-trade-{}-{}".format(exchange.id, pair),
                lambda: self.__trade(exchange, pair, wait_for_other_trade=True),
                should_terminate=True,
            )
        self.__books_lock.release()
        # TODO: Make this a call to `Log.data`.
        Log.info(fairs)

    def order_size(self, direction, fees, balance, fair, price):
        dir_ = 1 if direction == Direction.BUY else -1
        edge = ((fair.mean / price - 1) * dir_ - fees) / fair.stddev
        # Positive edge --> profitable order.
        desired_balance_value = edge * SIZE_PARAMETER * dir_
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
        mids = (bids + asks) / 2  # use mid price for target balance value calculations
        quote_currency = mids.index[0].quote

        gradient = fairs.gradient(mids) * fairs.mean
        balance_direction_vector = gradient / (np.linalg.norm(gradient) + 1e-100)
        target_balance_values = balance_direction_vector * fairs.z_score(mids) * size
        bal_no_quote = pd.Series(balances)
        bal_no_quote = (
            bal_no_quote.drop([quote_currency]) if quote_currency in bal_no_quote else bal_no_quote
        )
        pair_balances = bal_no_quote.rename(lambda c: TradingPair(c, quote_currency))
        proposed_orders = (target_balance_values / fairs.mean) - pair_balances
        prices = (proposed_orders >= 0) * asks + (proposed_orders < 0) * bids

        profitable = np.sign(proposed_orders) * (fairs.mean / prices - 1) > fees + min_edge
        profitable_orders = proposed_orders * profitable
        return profitable_orders
