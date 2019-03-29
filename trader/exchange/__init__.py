"""The `exchange` module.

Call the static method `Exchanges.get(EXCHANGE)` to retrieve a particular exchange object. If an
exchange instance already exists for a given exchange, it will be re-used.

"""

from trader.exchange.bitfinex import Bitfinex
from trader.exchange.kraken import Kraken
from trader.util.constants import BITFINEX, KRAKEN


class ExchangesError(Exception):
    pass


class Exchanges:
    __exchanges = {}
    __thread_manager = None
    __initializers = {
        KRAKEN: lambda: Kraken(Exchanges.__thread_manager),
        BITFINEX: lambda: Bitfinex(Exchanges.__thread_manager),
    }

    @staticmethod
    def set_thread_manager(thread_manager):
        Exchanges.__thread_manager = thread_manager

    @staticmethod
    def get(exchange):
        if Exchanges.__thread_manager is None:
            raise ExchangesError("static thread manager not set")
        if exchange not in Exchanges.__exchanges:
            initializer = Exchanges.__initializers[exchange]
            Exchanges.__exchanges[exchange] = initializer()
        return Exchanges.__exchanges[exchange]
