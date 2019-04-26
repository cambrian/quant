"""The `constants` module.

Constants to identify common entities in the code.

"""

# Exchanges.
BITFINEX = "bitfinex"
DUMMY = "dummy"
KRAKEN = "kraken"


class Currency:
    """A currency."""

    def __init__(self, id):
        self.__id = id

    def __repr__(self):
        return self.__id

    def json_value(self):
        return repr(self)

    def __lt__(self, other):
        return self.__id < other.__id

    def __deepcopy__(self, memo):
        return self


# Currencies.
USD = Currency("USD")
USDT = Currency("USDT")
BTC = Currency("BTC")
ETH = Currency("ETH")
XRP = Currency("XRP")
<<<<<<< HEAD
LTC = Currency("LTC")
EOS = Currency("EOS")
NEO = Currency("NEO")
=======
NEO = Currency("NEO")
LTC = Currency("LTC")
EOS = Currency("EOS")
>>>>>>> Fixing log bug, adding live bitfinex trading
STABLECOINS = {USD, USDT}


class TradingPair:
    """A trading pair."""

    def __init__(self, base, quote):
        if not isinstance(base, Currency):
            raise TypeError("base is not a tradable asset")
        if not isinstance(quote, Currency):
            raise TypeError("quote is not a tradable asset")
        self.__base = base
        self.__quote = quote

    @property
    def base(self):
        return self.__base

    @property
    def quote(self):
        return self.__quote

    def __repr__(self):
        return "{}-{}".format(self.__base, self.__quote)

    def json_value(self):
        return (self.__base.json_value(), self.__quote.json_value())

    # Make TradingPair instances sortable.
    def __lt__(self, other):
        if self.__base < other.__base:
            return True
        if self.__base == other.__base and self.__quote < other.__quote:
            return True
        return False

    def __ge__(self, other):
        return not self < other

    def __eq__(self, other):
        return self.base == other.base and self.quote == other.quote

    def __hash__(self):
        return id(self)

    def __deepcopy__(self, memo):
        return self


# USD quotes.
BTC_USD = TradingPair(BTC, USD)
ETH_USD = TradingPair(ETH, USD)
XRP_USD = TradingPair(XRP, USD)
LTC_USD = TradingPair(LTC, USD)
EOS_USD = TradingPair(EOS, USD)
NEO_USD = TradingPair(NEO, USD)

# USDT quotes.
BTC_USDT = TradingPair(BTC, USDT)
ETH_USDT = TradingPair(ETH, USDT)
XRP_USDT = TradingPair(XRP, USDT)
NEO_USDT = TradingPair(NEO, USDT)
LTC_USDT = TradingPair(LTC, USDT)
EOS_USDT = TradingPair(EOS, USDT)

# TODO: Maybe make this a static function `TradingPair.of`.
# Use instead of recreating a TradingPair from base currencies.
Pairs = {
    (BTC, USDT): BTC_USDT,
    (ETH, USDT): ETH_USDT,
    (XRP, USDT): XRP_USDT,
    (LTC, USDT): LTC_USDT,
    (EOS, USDT): EOS_USDT,
    (NEO, USDT): NEO_USDT,
    (BTC, USD): BTC_USD,
    (ETH, USD): ETH_USD,
    (XRP, USD): XRP_USD,
    (LTC, USD): LTC_USD,
    (EOS, USD): EOS_USD,
    (NEO, USD): NEO_USD,
    (USDT, USDT): None,
    (USD, USD): None,
}


def not_implemented():
    raise NotImplementedError("not implemented")
