from collections import defaultdict
from queue import Queue
from threading import Lock

from trader.util import Feed
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
                    exchange.book(pair).subscribe(
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
        Log.info(book)

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
        self.__books_lock.release()

        fairs = self.__latest_fairs
        if fairs is None:
            return

        ask = book.ask
        bid = book.bid
        balance = exchange.balances[pair.base()]
        fees = exchange.fees
        buy_size = (
            self.order_size(Direction.BUY, fees["taker"], balance, fairs, ask) if ask != None else 0
        )
        sell_size = (
            self.order_size(Direction.SELL, fees["taker"], balance, fairs, bid)
            if bid != None
            else 0
        )
        if buy_size > 0:
            Log.info("Buy: {}".format(buy_size))
            # order = exchange.add_order(pair, Direction.SELL, Order.Type.IOC, ask, buy_size)
            # Log.info(order)
        if sell_size > 0:
            Log.info("Sell: {}".format(sell_size))
            # TODO: Remove. In place now until strategy is implemented so we don't sell all BTC.
            # sell_size = max(0.004, sell_size / 1000)
            # order = exchange.add_order(pair, Direction.SELL, Order.Type.IOC, bid, sell_size)
            # Log.info(order)
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
        Log.info(fairs)

    def order_size(self, direction, fees, balance, fair, price):
        dir_ = 1 if direction == Direction.BUY else -1
        edge = ((fair.mean / price - 1) * dir_ - fees) / fair.stddev
        # Positive edge --> profitable order.
        desired_balance_value = edge * SIZE_PARAMETER * dir_
        proposed_order_size = (desired_balance_value / price - balance) * dir_
        return max(0, proposed_order_size)
