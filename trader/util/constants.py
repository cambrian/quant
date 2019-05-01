"""The `constants` module.

Constants to identify common entities in the code.

"""

from trader.util.types import Currency, TradingPair

# Exchanges.
BITFINEX = "bitfinex"
DUMMY = "dummy"
KRAKEN = "kraken"


# Currencies.
USD = Currency("USD")
USDT = Currency("USDT")
BTC = Currency("BTC")
ETH = Currency("ETH")
XRP = Currency("XRP")
LTC = Currency("LTC")
EOS = Currency("EOS")
NEO = Currency("NEO")
STABLECOINS = {USD, USDT}


<<<<<<< HEAD
=======
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

class ExchangePair:
    """A tuple of Exchange and TradingPair"""
    def __init__(self, exchange, pair):
        from trader.exchange.base import Exchange
        if not isinstance(exchange, Exchange):
            raise TypeError("exchange is not a valid exchange object")
        if not isinstance(pair, TradingPair):
            raise TypeError("pair is not a TradingPair")
        self.__exchange = exchange
        self.__pair = pair

    @property
    def exchange_id(self):
        return self.__exchange.id

    @property
    def quote(self):
        return self.__pair.quote

    @property
    def base(self):
        return self.__pair.base

    @property
    def pair(self):
        return self.__pair


>>>>>>> d298aa3db5fc61df5bf575592cab9c1063636fec
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


def not_implemented():
    raise NotImplementedError("not implemented")
