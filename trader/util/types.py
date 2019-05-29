"""The `types` module.

Miscellaneous wrapper types.

"""

from enum import Enum


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

    def __ge__(self, other):
        return not self < other

    def __eq__(self, other):
        if isinstance(other, Currency):
            return self.__id == other.__id
        return False

    def __hash__(self):
        return hash(self.__id)


class TradingPair:
    """A trading pair."""

    def __init__(self, base, quote):
        if not isinstance(base, Currency):
            raise TypeError("base is not a Currency")
        if not isinstance(quote, Currency):
            raise TypeError("quote is not a Currency")
        self.__base = base
        self.__quote = quote

    @property
    def base(self):
        return self.__base

    @property
    def quote(self):
        return self.__quote

    def __repr__(self):
        return f"{self.base}-{self.quote}"

    def json_value(self):
        return (self.base.json_value(), self.quote.json_value())

    def __lt__(self, other):
        if self.base < other.base:
            return True
        if self.base > other.base:
            return False
        if self.quote < other.quote:
            return True
        return False

    def __ge__(self, other):
        return not self < other

    def __eq__(self, other):
        return self.base == other.base and self.quote == other.quote

    def __hash__(self):
        return hash((self.base, self.quote))

    @staticmethod
    def parse(string):
        if not isinstance(string, str):
            return None
        pairs = string.split('-')
        if len(pairs) != 2:
            return None
        base = Currency(pairs[0])
        quote = Currency(pairs[1])
        return TradingPair(base, quote)


class ExchangePair:
    """A tuple of Exchange and TradingPair"""

    def __init__(self, exchange_id, pair):
        # TODO: check exchange_id for validity?
        if not isinstance(pair, TradingPair):
            raise TypeError("pair is not a TradingPair")
        self.__exchange_id = exchange_id
        self.__pair = pair

    @property
    def exchange_id(self):
        return self.__exchange_id

    @property
    def pair(self):
        return self.__pair

    @property
    def quote(self):
        return self.pair.quote

    @property
    def base(self):
        return self.pair.base

    def __repr__(self):
        return f"{self.exchange_id}-{self.base}-{self.quote}"

    def __lt__(self, other):
        if self.exchange_id < other.exchange_id:
            return True
        if self.exchange_id > other.exchange_id:
            return False
        if self.pair < other.pair:
            return True
        return False

    def __ge__(self, other):
        return not self < other

    def __eq__(self, other):
        return self.exchange_id == other.exchange_id and self.pair == other.pair

    def __hash__(self):
        return hash((self.exchange_id, self.pair))

    def json_value(self):
        return (self.exchange_id, self.pair.json_value())

    @staticmethod
    def parse(string):
        if isinstance(string, ExchangePair):
            return string
        if not isinstance(string, str):
            return None
        triple = string.split('-')
        if len(triple) != 3:
            return None
        exchange = triple[0]
        # Could call `pair_from_str`, but seems like more complexity for little reward
        base = Currency(triple[1])
        quote = Currency(triple[2])
        return ExchangePair(exchange, TradingPair(base, quote))



class OrderBook:
    """An immutable order book.

    TODO: Add actual levels to this book.

    Attributes:
        exchange_id (str): The id for this book's exchange.
        pair (Constant): The pair being traded.
        last_price (float): The last trade price.
        bid (float): Best bid price.
        ask (float): Best ask price.

    """

    def __init__(self, exchange_pair, last_price, bid, ask):
        self.__exchange_pair = exchange_pair
        self.__last_price = last_price
        self.__bid = bid
        self.__ask = ask

    def __eq__(self, other):
        return (
            type(self) == type(other)
            and self.__exchange_pair == other.__exchange_pair
            and self.__last_price == other.__last_price
            and self.__bid == other.__bid
            and self.__ask == other.__ask
        )

    @property
    def exchange_pair(self):
        return self.__exchange_pair

    @property
    def exchange_id(self):
        return self.exchange_pair.exchange_id

    @property
    def pair(self):
        return self.exchange_pair.pair

    @property
    def base(self):
        return self.exchange_pair.base

    @property
    def quote(self):
        return self.exchange_pair.quote

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
            "exchange_pair": self.exchange_pair.json_value(),
            "last_price": self.last_price,
            "bid": self.bid,
            "ask": self.ask,
        }


class Direction(Enum):
    """A trade direction."""

    BUY = 1
    SELL = 2


class Order:
    """An exchange_id agnostic representation of an order.

    Attributes:
        id (int): The order's exchange_id ID
        exchange_id (Exchange): The order's exchange_id.
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
        """An enum to be translated by each exchange_id."""

        MARKET = 1
        LIMIT = 2
        IOC = 3
        FOK = 4

    def __init__(self, id, exchange_id, pair, side, order_type, price, volume):
        self.__id = id
        self.__exchange_id = exchange_id
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
    def exchange_id(self):
        return self.__exchange_id

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
    # `update` fn that queries the exchange_id and updates accordingly. More complexity/time, though.
    def update_status(self, status):
        self.__status = status

    def __repr__(self):
        return "({}, {}, Order: #{}, Side: {}, Order Type: {}, Price: {}, Volume: {}, Status: {})".format(
            self.__exchange_id,
            self.__pair,
            self.__id,
            self.__side,
            self.__order_type,
            self.__price,
            self.__volume,
            self.__status,
        )
