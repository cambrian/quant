from collections import defaultdict
from queue import Queue
from threading import Lock

from trader.util import Feed
from trader.util.stats import Gaussian
from trader.util.types import Direction

SIZE_PARAMETER = 100


class Executor:
    """Given fair updates, listens to book updates and places orders to optimize our portfolio.

    NOTE: We lock `_trade_book` by exchange/pair such that calls to it are skipped if a lock cannot
    be acquired. However, this only applies to order ticks (new fairs prices should always run a
    cycle of orders).

    """

    def __init__(self, thread_manager, exchange_pairs):
        """Dummy-specific constructor.

        Args:
            exchange_pairs (dict): A dictionary indexed by exchange, consisting of the pairs from
                that exchange to execute on.

        """
        self.__books_lock = Lock()
        self.__trade_locks = defaultdict(Lock)
        self.__latest_books = defaultdict(None)
        self.__latest_fairs = None
        self.__thread_manager = thread_manager

        # Set up book feeds for every pair.
        for exchange, pairs in exchange_pairs.items():
            for pair in pairs:
                thread_manager.attach(
                    "executor-{}-{}".format(exchange.id, pair),
                    exchange.book(pair).subscribe(
                        lambda book: self.__tick_book(exchange, pair, book)
                    ),
                )

    def __tick_book(self, exchange, pair, book):
        self.__books_lock.acquire()
        self.__latest_books[(exchange, pair)] = book
        self.__books_lock.release()
        self.__trade(exchange, pair)

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
        book = self.__latest_books[(exchange, pair)]
        self.__books_lock.release()

        fairs = self.__latest_fairs
        if fairs is None:
            return

        ask = book.ask
        bid = book.bid
        balance = exchange.balances[pair.base]
        fees = exchange.fees
        # TODO: Change "buy" and "sell" to use the Direction enum.
        buy_size = self.order_size("buy", fees["taker"], balance, fairs, ask)
        sell_size = self.order_size("sell", fees["taker"], balance, fairs, bid)
        if buy_size > 0:
            print("Buy: {}".format(buy_size))
            # TODO: Write custom Bitfinex infra to use their immediate-or-cancel type.
            # exchange.add_order(pair, "buy", "exchange fill-or-kill", ask, buy_size)
            # update_balances(balances, fill)
        if sell_size > 0:
            print("Sell: {}".format(sell_size))
            # TODO: Remove. In place now until strategy is implemented so we don't sell all BTC.
            # sell_size = max(0.004, sell_size / 1000)
            # print(
            #     exchange.add_order(
            #         pair, SELL, "exchange immediate-or-cancel", str(bid), str(sell_size)
            #     )
            # )
        trade_lock.release()

    def tick_fairs(self, fairs):
        self.__latest_fairs = fairs
        for exchange, pair in self.__latest_books:
            self.__thread_manager.attach(
                "executor-fair-tick-{}-{}".format(exchange.id, pair),
                self.__trade(exchange, pair, wait_for_other_trade=True),
            )
        print(fairs)

    def order_size(self, direction, fees, balance, fair, price):
        dir_ = 1 if direction == Direction.BUY else -1
        edge = ((fair.mean / price - 1) * dir_ - fees) / fair.stddev
        # Positive edge --> profitable order.
        desired_balance_value = edge * SIZE_PARAMETER * dir_
        proposed_order_size = (desired_balance_value / price - balance) * dir_
        return max(0, proposed_order_size)
