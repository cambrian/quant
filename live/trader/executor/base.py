from trader.util import MVar

from abc import ABC, abstractmethod

_thread_count = 0


class Executor(ABC):
    def __init__(self, strategy_feed):
        global _thread_count
        self.__latest_input_var = MVar()
        self.__latest_input_var.stream(strategy_feed)

        def run():
            while True:
                latest_input = self.__latest_input_var.read()
                self._tick(latest_input)

        self.thread = (
            'executor-' + self.__class__.__name__.lower() + '-' + str(_thread_count), run)
        _thread_count += 1

    @abstractmethod
    def _tick(self, input):
        pass
