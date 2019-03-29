"""The `types` module.

Miscellaneous wrapper types.

"""

from enum import Enum


class OrderBook:
    """An immutable order book.

    TODO: Add actual levels to this book.

    Attributes:
        exchange (Constant): The book's exchange.
        pair (Constant): The pair being traded.
        last_price (float): The last trade price.
        bid (float): Best bid price.
        ask (float): Best ask price.

    """

    def __init__(self, exchange, pair, last_price, bid, ask):
        self.exchange = exchange
        self.pair = pair
        self.last_price = last_price
        self.bid = bid
        self.ask = ask

    def __repr__(self):
        return "({}, {}, Price: {}, Bid: {}, Ask: {})".format(
            self.exchange, self.pair, self.last_price, self.bid, self.ask
        )


class Direction(Enum):
    """A trade direction."""

    BUY = 1
    SELL = 2
