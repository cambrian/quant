from trader.util.thread import MVar

from abc import ABC, abstractmethod

_thread_count = 0


class MissingStrategyFeedError(Exception):
    pass


class Executor(ABC):
    """An abstract class for executing strategies.

    Args:
        thread_manager (ThreadManager): A thread manager to run feeds on.
        strategy_feeds (dict): A dict from strategy types to feeds for this executor to consume.

    """

    def __init__(self, thread_manager, strategy_feeds):
        self.__thread_manager = thread_manager
        latest_strategy_results_var = MVar()

        global _thread_count
        self.__id = _thread_count
        _thread_count += 1

        # Attach passed-in strategy feeds to the results variable.
        expected_strategy_feeds = self.expected_strategy_feeds()
        for strategy, results_feed in strategy_feeds.items():
            if strategy in expected_strategy_feeds:
                self.__attach_strategy_feed(
                    latest_strategy_results_var, strategy, results_feed)
                expected_strategy_feeds.remove(strategy)
            else:
                print('Ignoring the feed for strategy {strategy}.'.format(
                    strategy=strategy.__name__))

        # Ensure that we have all the feeds we expected.
        for strategy in expected_strategy_feeds:
            print('Missing the feed for strategy {strategy}.'.format(
                strategy=strategy.__name__))
        if len(expected_strategy_feeds) > 0:
            raise MissingStrategyFeedError('see output for details')

        def run():
            while True:
                latest_strategy_results = latest_strategy_results_var.read_on_write()
                self._tick(latest_strategy_results)

        self.thread = (
            'executor-' + self.__class__.__name__.lower() + '-' + str(_thread_count), run)
        _thread_count += 1

    def __attach_strategy_feed(self, strategy_results_var, strategy, results_feed):
        """Attaches a strategy feed for this executor to consume.

        Not a public method but documented here for clarity.

        Args:
            strategy_results_var (MVar): An MVar to place consumed results in.
            strategy (type): The strategy type.
            results_feed (Feed): A feed of results for that strategy type.

        """
        def update(results, latest_strategy_results):
            try:
                latest_results = latest_strategy_results[strategy]
            except KeyError:
                latest_results = {}
            for result_item in results:
                exchange = result_item[0]
                pair = result_item[1]
                if exchange not in latest_results:
                    latest_results[exchange] = {}
                if pair not in latest_results[exchange]:
                    latest_results[exchange][pair] = result_item[2]
                elif result_item[2]['timestamp'] > latest_results[exchange][pair]['timestamp']:
                    latest_results[exchange][pair] = result_item[2]
            return latest_results
        _, runner = results_feed.fold(update, {}, acc_var=strategy_results_var)
        runner_name = 'executor-{name}-{id}-strategy-{strategy}'.format(
            name=self.__class__.__name__.lower(), id=self.__id, strategy=strategy.__name__)
        self.__thread_manager.attach(runner_name, runner)

    @abstractmethod
    def expected_strategy_feeds(self):
        """The exact set of strategies expected by this executor.

        Returns:
            A set of strategy types.

        """
        pass

    @abstractmethod
    def _tick(self, latest_strategy_results):
        """Generates and executes orders when a strategy has new information.

        Args:
            latest_strategy_results (dict): A dictionary indexed by strategy, exchange and then
                pair. Each element contains the latest fair price and standard deviation that was
                received.

        """
        pass
