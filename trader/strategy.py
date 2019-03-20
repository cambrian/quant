from abc import ABC, abstractmethod

import rx.operators as op


class Strategy(ABC):
    def observe(self, data_feed):
        return data_feed.pipe(op.map(self._tick))

    @abstractmethod
    def _tick(self, data):
        # `data` is a dictionary of { pair: ohlcv }.
        # Returns a dictionary of { pair: (fair_price, std_dev) }.
        pass
