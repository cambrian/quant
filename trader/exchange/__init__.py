"""The `exchange` module.

Call the static method `Exchanges.get(EXCHANGE)` to retrieve a particular exchange object. If an
exchange instance already exists for a given exchange, it will be re-used.

"""

from trader.exchange.bitfinex import Bitfinex
from trader.exchange.kraken import Kraken
from trader.util.constants import BITFINEX, KRAKEN
