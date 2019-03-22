from trader.util import MVar

from abc import ABC, abstractmethod

_thread_count = 0


class Executor(ABC):
    """An abstract class for executing strategies.

    Attributes:
        thread (list): A thread to run the executor. Pass this to `manage_threads`.
        name (str): A canonical name for this exchange.

    Args:
        strategy_feed (Feed): A feed tuple containing a multicast Observable, obtained by running
            ticks of this strategy.

    """

    def __init__(self, strategy_feed):
        global _thread_count
        self.__latest_inputs_var = MVar()

        def update(latest_inputs, tick_data):
            if latest_inputs is None:
                latest_inputs = {}
            for tick_item in tick_data:
                exchange = tick_item[0]
                pair = tick_item[1]
                if exchange not in latest_inputs:
                    latest_inputs[exchange] = {}
                if pair not in latest_inputs[exchange]:
                    latest_inputs[exchange][pair] = tick_item[2]
                elif tick_item[2]['timestamp'] > latest_inputs[exchange][pair]['timestamp']:
                    latest_inputs[exchange][pair] = tick_item[2]
            return latest_inputs

        self.__latest_inputs_var.stream(strategy_feed, update)

        def run():
            while True:
                latest_inputs = self.__latest_inputs_var.read_on_write()
                self._tick(latest_inputs)

        self.thread = (
            'executor-' + self.__class__.__name__.lower() + '-' + str(_thread_count), run)
        _thread_count += 1

    @abstractmethod
    def _tick(self, strategy_inputs):
        """Generates and executes orders when a strategy has new information.

        Args:
            strategy_inputs (dict): A multi-level dictionary indexed by exchange and then pair. Each
                element contains the latest fair price and standard deviation.

        """
        pass
