from abc import ABC, abstractmethod


class Strategy(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def tick(self, data):
        # `data` is a dictionary of { pair: ohlcv }.
        # Returns a dictionary of { pair: (fair_price, std_dev) }.
        pass

    def consume(self, data_feed):
        return data_feed.map(self.tick)
