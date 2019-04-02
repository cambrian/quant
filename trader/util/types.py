"""The `types` module.

Miscellaneous wrapper types.

"""

from enum import Enum


class OrderBook:
    """An immutable order book.

    TODO: Add actual levels to this book.

    Attributes:
        exchange (Exchange): The book's exchange.
        pair (Constant): The pair being traded.
        last_price (float): The last trade price.
        bid (float): Best bid price.
        ask (float): Best ask price.

    """

    def __init__(self, exchange, pair, last_price, bid, ask):
        self.__exchange = exchange
        self.__pair = pair
        self.__last_price = last_price
        self.__bid = bid
        self.__ask = ask

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.__exchange == other.__exchange
            and self.__pair == other.__pair
            and self.__last_price == other.__last_price
            and self.__bid == other.__bid
            and self.__ask == other.__ask
        )

    @property
    def exchange(self):
        return self.__exchange.id

    @property
    def pair(self):
        return self.__pair

    @property
    def last_price(self):
        return self.__last_price

    @property
    def bid(self):
        return self.__bid

    @property
    def ask(self):
        return self.__ask

    def __repr__(self):
        return str(self.json_value())

    def json_value(self):
        return {
            "exchange": self.exchange,
            "pair": self.pair.json_value(),
            "last_price": self.last_price,
            "bid": self.bid,
            "ask": self.ask,
        }


class Direction(Enum):
    """A trade direction."""

    BUY = 1
    SELL = 2


class Order:
    """An exchange agnostic representation of an order.

    Attributes:
        id (int): The order's exchange ID
        exchange (Exchange): The order's exchange.
        pair (Constant): The order's traded pair.
        side (Direction): Side of the order book.
        order_type (Order.Type): Order fill type.
        price (float): Desired price to fill order (depends on order_type)
        volume (float): Desired volume to fill at price.

    """

    class Status(Enum):
        OPEN = 1
        CANCELLED = 2
        REJECTED = 3
        FILLED = 4

    class Type(Enum):
        """An enum to be translated by each exchange."""

        MARKET = 1
        LIMIT = 2
        IOC = 3
        FOK = 4

    def __init__(self, id, exchange, pair, side, order_type, price, volume):
        self.__id = id
        self.__exchange = exchange
        self.__pair = pair
        self.__side = side
        self.__order_type = order_type
        self.__price = price
        self.__volume = volume
        self.__status = self.Status.OPEN

    @property
    def id(self):
        return self.__id

    @property
    def exchange(self):
        return self.__exchange

    @property
    def pair(self):
        return self.__pair

    @property
    def side(self):
        return self.__side

    @property
    def order_type(self):
        return self.__order_type

    @property
    def price(self):
        return self.__price

    @property
    def volume(self):
        return self.__volume

    @property
    def status(self):
        return self.__status

    # TODO: Maybe remove so users cannot change status arbitrarily, instead just calling an
    # `update` fn that queries the exchange and updates accordingly. More complexity/time, though.
    def update_status(self, status):
        self.__status = status

    def __repr__(self):
        return "({}, {}, Order: #{}, Side: {}, Order Type: {}, Price: {}, Volume: {}, Status: {})".format(
            self.__exchange,
            self.__pair,
            self.__id,
            self.__side,
            self.__order_type,
            self.__price,
            self.__volume,
            self.__status,
        )
