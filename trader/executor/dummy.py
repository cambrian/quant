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
        pair = exchange.translate(pair)
        fees = exchange.fees
        buy_size = self.order_size(BUY, fees, balance, self.__fairs, ask)
        sell_size = self.order_size(SELL, fees, balance, self.__fairs, bid)
        # TODO: Logging
        # TODO: Uncomment when live, commented now so we don't buy/sell while testing
        if buy_size > 0:
            print("Buy: {}".format(buy_size))
            # buy_size = max(0.004, buy_size / 1000)
            # print(
            #     exchange.add_order(
            #         pair, BUY, "exchange immediate-or-cancel", str(ask), str(buy_size)
            #     )
            # )
        if sell_size > 0:
            print("Sell: {}".format(sell_size))
            # # TODO: remove, in place now until strategy is implemented to so we don't sell all BTC
            # sell_size = max(0.004, sell_size / 1000)
            # print(
            #     exchange.add_order(
            #         pair, SELL, "exchange immediate-or-cancel", str(bid), str(sell_size)
            #     )
            # )

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
