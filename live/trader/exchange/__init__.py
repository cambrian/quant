"""The `exchange` module.

Attributes:
    exchanges (dict): A singleton dictionary containing instances for all supported exchanges.

"""

from trader.constants import BITFINEX
from trader.constants import KRAKEN
from trader.exchange.bitfinex import Bitfinex
from trader.exchange.kraken import Kraken

exchanges = {
    KRAKEN: Kraken(),
    BITFINEX: Bitfinex()
}
