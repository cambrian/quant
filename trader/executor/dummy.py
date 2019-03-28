from trader.exchange import Exchanges
from trader.executor.base import Executor
from trader.util import Feed
from trader.util.constants import base_currency


class Dummy(Executor):
    """A shitty executor for testing purposes."""

    def __init__(self):
        self.__fairs = {}

    def tick_book(self, book):
        (exchange_name, pair, (bid, ask)) = book
        exchange = Exchanges.get(exchange_name)
        balance = exchange.balances[base_currency(pair)]
        fees = exchange.fees
        buy_size = self.order_size("buy", fees, balance, self.__fairs, ask)
        sell_size = self.order_size("sell", fees, balance, self.__fairs, bid)
        if buy_size > 0:
            # TODO: Approximate immediate-or-cancel, or choose another order_type (Bitfinex only
            # supports FOK).
            exchange.add_order(pair, "buy", "exchange fill-or-kill", ask, buy_size)
            # update_balances(balances, fill)
        if sell_size > 0:
            exchange.add_order(pair, "sell", "exchange fill-or-kill", bid, sell_size)
            # update_balances(balances, fill)

    def tick_fairs(self, fairs):
        # TODO: Have this run the order loop.
        self.__fairs = fairs

    # TODO
    def order_size(self, direction, fees, balance, fair, price):
        return 0.000
