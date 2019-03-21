from util import MVar

from abc import ABC, abstractmethod


class Executor(ABC):
    def __init__(self):
        self.__latest_input_var = MVar()

    def consume(self, input_feed):
        self.__latest_input_var.stream(input_feed)

    def run(self):
        while True:
            latest_input = self.__latest_input_var.read()
            self._tick(latest_input)

    @abstractmethod
    def _tick(self, input):
        pass
