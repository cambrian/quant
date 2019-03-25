from trader.util import MVar

from abc import ABC, abstractmethod
from datetime import datetime
from queue import Queue

import rx
import rx.operators as op

_thread_count = 0


class Strategy(ABC):
    """An abstract class for writing strategies.

    Attributes:
        feed (Feed): A feed tuple containing a multicast Observable, obtained by running ticks of
            this strategy.
        thread (list): A thread to run the executor. Pass this to `manage_threads`.

    Args:
        strategy_feed (Feed): A feed tuple containing an Observable, obtained by running ticks of a
            strategy.

    """

    def __init__(self, *data_feeds):
        global _thread_count
        tick_queue = Queue()
        consuming = {}

        # Populate tick queue with data feeds.
        for (exchange, pair, feed) in data_feeds:
            if (exchange, pair) not in consuming:
                consuming[(exchange, pair)] = True
                feed.subscribe_(
                    lambda ohlcv, exchange=exchange, pair=pair:
                        tick_queue.put((exchange, pair, ohlcv)))

        def feed_generator():
            while True:
                exchange, pair, ohlcv = tick_queue.get()
                tick_data = self._tick(exchange, pair, ohlcv)
                timestamp = datetime.now()
                for i in range(len(tick_data)):
                    tick_data[i][2]['timestamp'] = timestamp
                yield tick_data

        self.feed = rx.from_iterable(feed_generator()).pipe(op.publish())
        self.thread = ('strategy-' + self.__class__.__name__.lower() + '-' + str(_thread_count),
                       self.feed.connect)
        _thread_count += 1

    @abstractmethod
    def _tick(self, exchange, pair, ohlcv):
        """The actual implementation of a strategy.

        Strategies should take the feed data received at each tick and incorporate it into their
        running models of the market.

        Args:
            exchange (str): The exchange for this feed data.
            pair (str): The pair for this feed data.
            ohlcv (dict): A dictionary with `timestamp`, `open`, `high`, `low`, `close`, and
                `volume`, which represents a candle for the given pair and exchange. The strategy
                will implicitly expect these candles on a particular time interval.

        Returns:
            A list of strategy updates (exchange, pair, {fair_price, std_dev, [auxiliary_data]}) for
            different exchanges/pairs.

        """
        pass
