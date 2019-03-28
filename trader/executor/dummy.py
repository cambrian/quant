from trader.exchange import Exchanges
from trader.executor.base import Executor
from trader.util import Feed
from trader.util.constants import BUY, SELL, SIZE, base_currency
from trader.util.stats import Gaussian


class Dummy(Executor):
    """A shitty executor for testing purposes."""

    def __init__(self):
        self.__fairs = Gaussian([0], [0])

    def tick_book(self, book):
        (exchange_name, pair, (bid, ask)) = book
        exchange = Exchanges.get(exchange_name)
        balance = exchange.balances[base_currency(pair)]
        fees = exchange.fees
        buy_size = self.order_size(BUY, fees, balance, self.__fairs, ask[0])
        sell_size = self.order_size(SELL, fees, balance, self.__fairs, bid[0])
        if buy_size > 0:
            # TODO: Try Immediate-or-cancel
            # TODO: Fix add_order
            print("BUY: {}".format(buy_size))
            # exchange.add_order(pair, BUY, "exchange fill-or-kill", ask, buy_size)
        if sell_size > 0:
            print("SELL: {}".format(sell_size))
            # exchange.add_order(pair, SELL, "exchange fill-or-kill", bid, sell_size)

    def tick_fairs(self, fairs):
        # TODO: Have this run the order loop.
        self.__fairs = fairs

    def order_size(self, direction, fees, balance, fair, price):
        """Fair is a Gaussian. Returns order size in base currency"""
        # TODO: Handle difference in maker/taker fee
        dir_ = 1 if direction == BUY else -1
        edge = ((fair.mean / price - 1) * dir_ - fees["taker"]) / fair.stddev
        # positive edge --> profitable order
        desired_balance_value = edge * SIZE * dir_
        proposed_order_size = (desired_balance_value / price - balance) * dir_
        return max(0, proposed_order_size)
