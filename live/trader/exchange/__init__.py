"""The `exchange` module.

Call the static method `Exchanges.get(EXCHANGE)` to retrieve a particular exchange object. If an
exchange instance already exists for a given exchange, it will be re-used.

"""

from trader.exchange.bitfinex import Bitfinex
from trader.exchange.kraken import Kraken
from trader.util.constants import BITFINEX
from trader.util.constants import KRAKEN


class Exchanges:
    _exchanges = {}
    _initializers = {
        KRAKEN: lambda: Kraken(),
        BITFINEX: lambda: Bitfinex()
    }

    @staticmethod
    def get(exchange):
        if exchange not in Exchanges._exchanges:
            initializer = Exchanges._initializers[exchange]
            Exchanges._exchanges[exchange] = initializer()
        return Exchanges._exchanges[exchange]
