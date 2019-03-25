from trader.util import Feed
from trader.util.thread import MVar

from abc import ABC, abstractmethod
from datetime import datetime
from queue import Queue

_thread_count = 0


class MissingPriceFeedError(Exception):
    pass


class Strategy(ABC):
    """An abstract class for writing strategies.

    Attributes:
        feed (Feed): A feed obtained by running ticks of this strategy.

    Args:
        thread_manager (ThreadManager): A thread manager to run feeds on.
        price_feeds (dict): A dict from price feed info tuples (see `expected_price_feeds`) to price
            feeds for this strategy to consume.

    """

    def __init__(self, thread_manager, price_feeds):
        self.__thread_manager = thread_manager
        self.__update_queue = Queue()

        global _thread_count
        self.__id = _thread_count
        _thread_count += 1

        # Attach passed-in price feeds to the update queue.
        expected_price_feeds = self.expected_price_feeds()
        for (exchange, pair, time_interval), ohlcv_feed in price_feeds.items():
            if (exchange, pair, time_interval) in expected_price_feeds:
                self.__attach_price_feed(
                    exchange, pair, time_interval, ohlcv_feed)
                expected_price_feeds.remove((exchange, pair, time_interval))
            else:
                print('Ignoring the {pair} ({time_interval}) feed on {exchange}.'.format(
                    pair=pair, time_interval=str(time_interval), exchange=exchange))

        # Ensure that we have all the feeds we expected.
        for (exchange, pair, time_interval) in expected_price_feeds:
            print('Missing the {pair} ({time_interval}) feed on {exchange}.'.format(
                pair=pair, time_interval=str(time_interval), exchange=exchange))
        if len(expected_price_feeds) > 0:
            raise MissingPriceFeedError('see output for details')

        def feed_generator():
            while True:
                results = self.__update_queue.get()()
                timestamp = datetime.now()
                for i in range(len(results)):
                    results[i][2]['timestamp'] = timestamp
                yield results

        self.__feed = Feed(feed_generator())
        feed_name = 'strategy-{name}-{id}'.format(
            name=self.__class__.__name__.lower(), id=self.__id)
        thread_manager.attach(feed_name, self.__feed.run)

    def __attach_price_feed(self, exchange, pair, time_interval, ohlcv_feed):
        """Attaches a price feed for this strategy to consume.

        Not a public method but documented here for clarity.

        Args:
            exchange (str): The exchange for this feed data.
            pair (str): The pair for this feed data, specified in the format of the exchange.
            time_interval: The time interval for this feed data, specified in the format of the
                exchange.
            ohlcv_feed (Feed): A feed with OHLCV data (see `tick`).

        """
        def enqueue(ohlcv):
            def update():
                self._tick(exchange, pair, time_interval, ohlcv)
            return update
        runner = ohlcv_feed.observe(enqueue)
        runner_name = 'strategy-{name}-{id}-feed-{exchange}-{pair}-{time_interval}'.format(
            name=self.__class__.__name__.lower(), id=self.__id, exchange=exchange, pair=pair,
            time_interval=str(time_interval))
        self.__thread_manager.attach(runner_name, runner)

    @property
    def feed(self):
        return self.__feed

    @abstractmethod
    def expected_price_feeds(self):
        """The exact set of price feeds expected by this strategy.

        Returns:
            A set of feed info tuples (exchange, pair, time_interval).

        """
        pass

    @abstractmethod
    def _tick(self, exchange, pair, time_interval, ohlcv):
        """The actual implementation of a strategy.

        Strategies should take the feed data received at each tick and incorporate it into their
        running models of the market.

        Args:
            exchange (str): The exchange for this feed data.
            pair (str): The pair for this feed data, specified in the format of the exchange.
            time_interval: The time interval for this feed data, specified in the format of the
                exchange.
            ohlcv (dict): A dictionary with `timestamp`, `open`, `high`, `low`, `close`, and
                `volume`, which represents a candle for the given pair and exchange. The strategy
                will implicitly expect these candles on a particular time interval.

        Returns:
            A list of strategy results (exchange, pair, {fair_price, std_dev, [auxiliary_data]}) for
            different exchanges/pairs.

        """
        pass
