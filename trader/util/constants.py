"""The `constants` module.

Constants to identify common entities in the code.

"""

# Exchanges.
BITFINEX = "bitfinex"
KRAKEN = "kraken"


class Currency:
    """A currency."""

    def __init__(self, id):
        self.__id = id

    def __repr__(self):
        return self.__id


# Currencies.
USD = Currency("USD")
USDT = Currency("USDT")
BTC = Currency("BTC")
ETH = Currency("ETH")
XRP = Currency("XRP")


class TradingPair:
    """A trading pair."""

    def __init__(self, base, quote):
        if not isinstance(base, Currency):
            raise TypeError("base is not a tradable asset")
        if not isinstance(quote, Currency):
            raise TypeError("quote is not a tradable asset")
        self.__base = base
        self.__quote = quote

    def base(self):
        return self.__base

    def quote(self):
        return self.__quote

    def __repr__(self):
        return "{}-{}".format(self.__base, self.__quote)


# USD quotes.
BTC_USD = TradingPair(BTC, USD)
ETH_USD = TradingPair(ETH, USD)
XRP_USD = TradingPair(XRP, USD)

# USDT quotes.
BTC_USDT = TradingPair(BTC, USDT)
ETH_USDT = TradingPair(ETH, USDT)
XRP_USDT = TradingPair(XRP, USDT)


def not_implemented():
    raise NotImplementedError("not implemented")
