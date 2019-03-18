from abc import ABC, abstractmethod
import rx


class Exchange(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def _feed(self, pairs, time_interval):
        # Repeatedly `yield` new data at each tick.
        pass

    def observe(self, pairs, time_interval):
        feed_generator = self._feed(pairs, time_interval)
        return rx.from_iterable(feed_generator)
