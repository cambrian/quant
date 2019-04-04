from collections import defaultdict

from trader.util.constants import STABLECOINS


class Metrics:
    """Tracks and logs metrics during execution.

    TODO: Ensure that `__tick_balances` works and write a simple PnL tracker to get run.

    Args:
        thread_manager (ThreadManager): A thread manager to attach any child threads.
        exchanges (set): A set of exchange objects we are trading on.

    """

    def __init__(self, thread_manager, exchanges):
        self.__thread_manager = thread_manager
        self.__balances = {}
        self.__prices = {}

        # Set up balance feeds.
        for exchange in exchanges:
            thread_manager.attach(
                "metrics-{}".format(exchange.id),
                exchange.balances_feed().subscribe(
                    # Ugly but otherwise the values of exchange/balances will get overwritten in
                    # the closure at every iteration...
                    lambda balances, exchange=exchange: self.__tick_balances(exchange, balances)
                ),
            )

    def __tick_balances(self, exchange, balances):
        for currency, balance in balances.items():
            self.__balances[(exchange, currency)] = balance
        non_stablecoins = [c for c in balances.keys() if c not in STABLECOINS]
        prices = exchange.prices(non_stablecoins)
        for currency in non_stablecoins:
            self.__prices[(exchange, currency)] = prices.at["close", currency]
