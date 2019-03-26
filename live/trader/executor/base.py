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
                    strategy=strategy.__name__.lower()))

        # Ensure that we have all the feeds we expected.
        for strategy in expected_strategy_feeds:
            print('Missing the feed for strategy {strategy}.'.format(
                strategy=strategy.__name__.lower()))
        if len(expected_strategy_feeds) > 0:
            raise MissingStrategyFeedError('see output for details')

        def runner():
            while True:
                latest_strategy_results = latest_strategy_results_var.read_on_write()
                self._tick(latest_strategy_results)

        runner_name = 'executor-{name}-{id}'.format(
            name=self.__class__.__name__.lower(), id=self.__id)
        self.__thread_manager.attach(runner_name, runner)

    def __attach_strategy_feed(self, strategy_results_var, strategy, results_feed):
        """Attaches a strategy feed for this executor to consume.

        Not a public method but documented here for clarity.

        Args:
            strategy_results_var (MVar): An `MVar` to accumulate consumed results in.
            strategy (type): The strategy type.
            results_feed (Feed): A feed of results for that strategy type.

        """
        # TODO: Clean this function up?
        def merge(results, latest_results):
            if strategy not in latest_results:
                latest_results[strategy] = {}
            for result_item in results:
                exchange = result_item[0]
                pair = result_item[1]
                if exchange not in latest_results[strategy]:
                    latest_results[strategy][exchange] = {}
                if pair not in latest_results[strategy][exchange]:
                    latest_results[strategy][exchange][pair] = result_item[2]
                elif (result_item[2]['timestamp'] >
                      latest_results[strategy][exchange][pair]['timestamp']):
                    latest_results[strategy][exchange][pair] = result_item[2]
            return latest_results

        _, runner = results_feed.fold(merge, {}, acc_var=strategy_results_var)
        runner_name = 'executor-{name}-{id}-strategy-{strategy}'.format(
            name=self.__class__.__name__.lower(), id=self.__id, strategy=strategy.__name__.lower())
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
