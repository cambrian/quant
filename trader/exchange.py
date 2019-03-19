from abc import ABC, abstractmethod
from aiostream import stream


class Exchange(ABC):
    # TODO: Trading/account management functions.
    def observe(self, pairs, time_interval):
        feed_generator = self._feed(pairs, time_interval)
        return stream.iterate(feed_generator)

    @abstractmethod
    def _feed(self, pairs, time_interval):
        # Repeatedly `yield` new data at each tick.
        pass
