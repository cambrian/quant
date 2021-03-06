from collections import defaultdict
from queue import Queue

from trader.exchange.base import Exchange, ExchangeError
from trader.util import Feed, Log
from trader.util.constants import not_implemented
from trader.util.types import (BookLevel, ExchangePair, OpenOrder, OrderBook,
                               Side)


def dummy_exchanges(thread_manager, data):
    exchange_ids = {ep.exchange_id for ep in data.iloc[0].index}
    return [DummyExchange(thread_manager, e, data) for e in exchange_ids]


class DummyExchange(Exchange):
    """
    Dummy exchange to simulate a single base exchange. Uses historical data and executes orders at
    last trade price.
    data may contain pairs for other base exchanges but they will be ignored.
    """

    def __init__(self, thread_manager, id, data, fees={"maker": 0.001, "taker": 0.002}):
        super().__init__(thread_manager)
        self.__data = data
        self.__id = id
        self.__supported_pairs = [ep.pair for ep in data.columns.unique(0)]
        # `time` is not private to allow manual adjustment.
        self.time = -1
        self.__fees = fees
        self.__book_queues = {pair: Queue() for pair in self.__supported_pairs}
        self.__book_feeds = {}
        self.__latest_books = {}
        self.__positions = defaultdict(float)
        self.__order_id = 0
        for pair in self.__supported_pairs:
            pair_feed, runner = Feed.of(self.__book_generator(pair))
            self._thread_manager.attach("dummy-{}-book".format(pair), runner)
            self.__book_feeds[pair] = pair_feed

    @property
    def id(self):
        return self.__id

    @staticmethod
    def encode_trading_pair(pair):
        not_implemented()
        # return repr(pair)

    @staticmethod
    def decode_trading_pair(pair_string):
        not_implemented()
        # return TradingPair.parse(pair_string)

    def step_time(self):
        """Returns False if all data has been exhausted."""
        self.time += 1
        if self.time >= len(self.__data.index):
            return False
        frame = self.__data.iloc[self.time]
        for ep, price in frame.xs("price", level=1).iteritems():
            if ep.exchange_id != self.id:
                continue
            ep = ExchangePair(self.id, ep.pair)
            dummy_book = OrderBook(ep, [BookLevel(price, 1)], [BookLevel(price, 1)])
            self.__book_queues[ep.pair].put(dummy_book)
            self.__latest_books[ep.pair] = dummy_book
        Log.info("dummy-step", self.time)
        return True

    def book_feed(self, pair):
        if pair not in self.__supported_pairs:
            raise ExchangeError("pair not supported by " + self.id)
        return self.__book_feeds[pair]

    def __book_generator(self, pair):
        while True:
            book = self.__book_queues[pair].get()
            yield book

    def frame(self, pairs):
        eps = [ExchangePair(self.id, pair) for pair in pairs]
        return self.__data.iloc[self.time][eps]

    def get_warmup_data(self, pairs, duration, resolution):
        return []

    # TODO
    def positions_feed(self):
        pass

    @property
    def positions(self):
        return self.__positions

    @property
    def fees(self):
        return self.__fees

    def add_order(self, order):
        net_size = order.size * (1 if order.side == Side.BUY else -1)
        self.__positions[order.pair.base] += net_size
        self.__positions[order.pair.quote] -= (
            net_size + order.size * self.__fees["taker"]
        ) * order.price
        Log.info("dummy order", order)
        Log.info("dummy positions", self.__positions)
        return OpenOrder(order, order.id)

    # Unnecessary since orders are immediate.
    def cancel_order(self, order_id):
        not_implemented()

    # Unnecessary since orders are immediate.
    def get_open_positions(self):
        not_implemented()
