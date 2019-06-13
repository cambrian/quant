from copy import deepcopy
from threading import Lock

import pandas as pd

from trader.util import Log
from trader.util.types import ExchangePair, Order, Side


class Executor:
    """Given fair updates, listens to book updates and places orders to optimize our portfolio.

    NOTE: We lock `__trade` by exchange/pair such that calls to it are skipped if a lock cannot
    be acquired. However, this only applies to order ticks (new fairs prices should always run a
    cycle of orders).

    Args:
        thread_manager (ThreadManager): A thread manager to attach any child threads for this
            executor object.
        exchanges_and_pairs (dict): A dictionary indexed by exchange, consisting of the pairs from
            that exchange to execute on.
        execution_strategy (ExecutionStrategy)

    """

    def __init__(self, thread_manager, exchanges_and_pairs, execution_strategy):
        self.__trade_lock = Lock()
        self.__books_lock = Lock()
        self.__latest_fairs = None
        self.__thread_manager = thread_manager
        self.__exchange_pairs = [
            ExchangePair(e.id, p) for e, ps in exchanges_and_pairs.items() for p in ps
        ]
        self.__exchanges = {e.id: e for e in exchanges_and_pairs}
        self.__order_id_counter = 0
        self.__latest_books = {ep: None for ep in self.__exchange_pairs}
        self.execution_strategy = execution_strategy

        # Set up book feeds for every pair.
        for ep in self.__exchange_pairs:
            thread_manager.attach(
                "executor-{}".format(ep),
                self.__exchanges[ep.exchange_id].book_feed(ep.pair).subscribe(self.__tick_book),
            )

    def __tick_book(self, book):
        self.__books_lock.acquire()
        self.__latest_books[book.exchange_pair] = book
        # Log.warn("new book", book.exchange_pair)
        self.__books_lock.release()

    def __trade(self, wait_for_other_trade=False):
        """
        If `wait_for_other_trade` is false, doesn't try to trade if there is another thread
        attempting to trade. If true, it will wait for the other thread to finish and try
        immediately after.
        TODO: requires that __latest_fairs and self.__exchange_pairs have the same indexing. Make
        this explicit or don't require it.
        """
        if self.__latest_fairs is None:
            Log.warn("Attempted to trade but latest_fairs is None.")
            return

        # component warmup may not be synchronized
        for ep in self.__latest_fairs.mean.index:
            if self.__latest_books[ep] is None:
                Log.warn("No book data for exchange pair:", ep)
                return

        if wait_for_other_trade:
            self.__trade_lock.acquire()
        elif not self.__trade_lock.acquire(blocking=False):
            Log.debug("Other thread trading.")
            return
        Log.info("Trading.")

        bids = pd.Series(index=self.__latest_fairs.mean.index)
        asks = pd.Series(index=self.__latest_fairs.mean.index)
        fees = pd.Series(index=self.__latest_fairs.mean.index)
        positions = {}
        # self.__books_lock.acquire()
        for exchange_pair in self.__latest_fairs.mean.index:
            exchange = self.__exchanges[exchange_pair.exchange_id]
            book = self.__latest_books[exchange_pair]
            bids[exchange_pair] = book.bids[0].price
            asks[exchange_pair] = book.asks[0].price
            fees[exchange_pair] = exchange.fees["taker"]
            positions[exchange.id, exchange_pair.base] = exchange.positions[exchange_pair.base] or 0
        # self.__books_lock.release()
        positions = pd.Series(positions)
        print("Positions", positions)

        order_sizes = self.execution_strategy.tick(positions, bids, asks, self.__latest_fairs, fees).fillna(0.0)
        print("Order size", order_sizes)

        for exchange_pair, order_size in order_sizes.items():
            if order_size == 0:
                continue
            exchange = self.__exchanges[exchange_pair.exchange_id]
            side = Side.BUY if order_size > 0 else Side.SELL
            price = (asks if order_size > 0 else bids)[exchange_pair]
            order = Order(
                self.__next_order_id(), exchange_pair, side, Order.Type.IOC, price, abs(order_size)
            )
            exchange.add_order(order)  # TODO: require this to be async?
            Log.info("sent order", order)
        self.__trade_lock.release()

    def tick_fairs(self, fairs):
        self.__latest_fairs = fairs
        self.__thread_manager.attach("executor-fairs", self.__trade, should_terminate=True)

    def __next_order_id(self):
        self.__order_id_counter += 1
        return self.__order_id_counter
