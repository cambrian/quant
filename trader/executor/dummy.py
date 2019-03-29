from collections import defaultdict
from queue import Queue
from threading import Lock

from trader.exchange import Exchanges
from trader.executor.base import Executor
from trader.util import Feed
from trader.util.stats import Gaussian
from trader.util.types import Direction

SIZE_PARAMETER = 100


class Dummy(Executor):
    """A shitty executor for testing purposes.

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
        super().__init__(thread_manager)
        self.__trade_locks = defaultdict(Lock)
        self.__latest_books = defaultdict(None)
        self.__latest_fairs = None

        # Set up book feeds for every pair.
        for exchange_id in exchange_pairs:
            exchange = Exchanges.get(exchange_id)
            for pair in exchange_pairs[exchange_id]:
                thread_manager.attach(
                    "executor-{}-{}".format(exchange_id, pair),
                    exchange.book(pair).subscribe(
                        lambda book, exchange_pair=(exchange, pair): self.__tick_book(
                            exchange_pair, book
                        )
                    ),
                )

    def __tick_book(self, exchange_pair, book):
        # De-dupe order book ticks by bid and ask.
        # Consider moving this logic elsewhere?
        if exchange_pair in self.__latest_books:
            current_book = self.__latest_books[exchange_pair]
            if book.bid == current_book.bid and book.ask == current_book.ask:
                self.__latest_books[exchange_pair] = book
                return
        self.__latest_books[exchange_pair] = book
        lock = self.__trade_locks[exchange_pair]
        lock_acquired = lock.acquire(False)
        if lock_acquired:
            self._trade_book(book)
            lock.release()
        print(book)

    def _trade_book(self, book):
        pair = book.pair
        ask = book.ask
        bid = book.bid
        fairs = self.__latest_fairs
        if fairs is None:
            return
        exchange = Exchanges.get(book.exchange)
        balance = exchange.balances[pair.base]
        fees = exchange.fees
        # TODO: Change "buy" and "sell" to use the Direction enum.
        buy_size = self.order_size("buy", fees, balance, fairs, ask)
        sell_size = self.order_size("sell", fees, balance, fairs, bid)
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

    def tick_fairs(self, fairs):
        self.__latest_fairs = fairs
        for exchange_pair, book in self.__latest_books.items():
            lock = self.__trade_locks[exchange_pair]
            lock.acquire()
            self._trade_book(book)
            lock.release()
        print(fairs)

    def order_size(self, direction, fees, balance, fair, price):
        # TODO: Handle difference in maker/taker fee.
        dir_ = 1 if direction == Direction.BUY else -1
        edge = ((fair.mean / price - 1) * dir_ - fees["taker"]) / fair.stddev
        # Positive edge --> profitable order.
        desired_balance_value = edge * SIZE_PARAMETER * dir_
        proposed_order_size = (desired_balance_value / price - balance) * dir_
        return max(0, proposed_order_size)
