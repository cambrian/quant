from collections import defaultdict
from queue import Queue
from threading import Lock

import numpy as np
import pandas as pd

from trader.util import Feed, Gaussian, Log
from trader.util.types import Direction, ExchangePair, Order, TradingPair


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
        execution_strategy (ExecutionStrategy)

    """

    def __init__(self, thread_manager, exchange_pairs, execution_strategy):
        self.__books_lock = Lock()
        self.__trade_lock = Lock()
        self.__latest_books = {}  # keyed by (Exchange.id, pair)
        self.__latest_fairs = None
        self.__thread_manager = thread_manager
        self.__exchange_pairs = [
            ExchangePair(e.id, p) for e, ps in exchange_pairs.items() for p in ps
        ]
        self.__exchanges = {e.id: e for e in exchange_pairs}
        self.execution_strategy = execution_strategy

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
        self.__latest_books[exchange_pair] = book
        self.__books_lock.release()
        # TODO: think about how to do this
        # self.__thread_manager.attach("executor-book", lambda: self.__trade(), should_terminate=True)
        Log.info("executor-book", book)

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
            bids[exchange_pair] = book.bids[0].price
            asks[exchange_pair] = book.asks[0].price
            fees[exchange_pair] = exchange.fees["taker"]
            balances[exchange.id, exchange_pair.base] = exchange.balances[exchange_pair.base] or 0
        self.__books_lock.release()
        balances = pd.Series(balances)

        orders = self.execution_strategy.tick(balances, bids, asks, self.__latest_fairs, fees)
        Log.info("executor_orders {}".format(orders))

        # TODO: use order type
        for exchange_pair, order_size in orders.items():
            exchange = self.__exchanges[exchange_pair.exchange_id]
            if order_size < 0:
                order_size = abs(order_size)
                # if order_size > exchange.balances[exchange_pair.base]:
                #     order_size = exchange.balances[exchange_pair.base]
                if order_size > 0:
                    Log.info("executor-sell", {"pair": exchange_pair, "size": order_size})
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
                    Log.info("executor-buy", {"pair": exchange_pair, "size": order_size})
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
