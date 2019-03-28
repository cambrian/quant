from trader.exchange import Exchanges
from trader.executor.base import Executor
from trader.util import Feed


def base_currency(pair):
    return pair.split('/')[0]


class Dummy(Executor):
    """A shitty executor for testing purposes."""

    def __init__(self):
        self.__fairs = {}

    def tick(self, fairs):
        self.__fairs = fairs

    def main(self, stream_val):
        (exchange_name, pair, (bid, ask)) = stream_val
        exchange = Exchanges.get(exchange_name)
        # TODO: Synchro needed to maintain balance between ordering and next update
        # Also gets rate-limited currently
        balance = exchange.get_balance()[base_currency(pair)]
        fees = exchange.fees
        buy_size = self.order_size('buy', fees, balance, self.__fairs, ask)
        sell_size = self.order_size('sell', fees, balance, self.__fairs, bid)
        if buy_size > 0:
            # TODO: approximate immediate-or-cancel, or chose another order_type
            exchange.add_order(pair, 'buy', 'exchange fill-or-kill', ask, buy_size)
            # update_balances(balances, fill)
        if sell_size > 0:
            exchange.add_order(pair, 'sell', 'exchange fill-or-kill', bid, sell_size)
            # update balances(balances, fill)

    # TODO
    def order_size(self, direction, fees, balance, fair, price):
        return 0.000
