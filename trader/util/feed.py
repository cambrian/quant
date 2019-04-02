import itertools
import time
from functools import partial, reduce
from queue import Full, Queue
from threading import Thread

from trader.util.thread import MVar, ThreadManager


class Feed:
    """A multicast stream type for Python.

    NOTE: The constructor is private. Use `Feed.of(iterable)` to construct a feed and its runner.

    Transformations of a feed (such as `map` or `filter`) return both a result and a function to run
    the transformation on a separate thread.

    TODO: Allow transformations that change the iterable on the same thread. This makes the library
    less mistake-proof, since `feed.map(foo)` might have unexpected behavior if `feed.map_in_place`
    (for example) is called later on.

    """

    class Error(Exception):
        pass

    # Hacky solution to prevent manual construction.
    __private = object()

    # Sentinel value for the end of items in a feed (None is more conventional, but may lead to
    # unexpected results if people want to use None in their feeds).
    __end = object()

    def __init__(self, private, iterable, initializer=None):
        if private != Feed.__private:
            raise Feed.Error("constructor is private")
        self.__iterable = iterable
        self.__initializer = initializer
        self.__sinks = []
        self.__done = False

    @staticmethod
    def of(iterable):
        """Static constructor for Feed.

        Args:
            iterable: An iterable to initialize the feed from.

        Returns:
            (Feed, Function): The feed and a function to run the feed's iterable.

        """
        feed = Feed(Feed.__private, iterable)
        return (feed, feed._run)

    def _sink(self, transform, buffer_size=None, attach_lazy=True):
        """Creates a new feed by transforming the iterable of this feed.

        Prefer calling `map`, `filter`, or any of the other specialized versions of this method.

        Args:
            transform (Function): A function that transforms an iterable into a new iterable.
            buffer_size (int): An argument to bound the size of the sink queue. This is useful when
                you do not want the parent writer feed to outpace the child reader feed.
            attach_lazy (bool): When True, items will not be placed in the sink queue until the
                transformed feed is actually run.

        Returns:
            (Feed, Function): The transformed result feed and a function to run the transformation.

        """
        feed_queue = Queue(maxsize=0 if buffer_size is None else buffer_size)

        def initializer():
            if self.__done:
                feed_queue.put(Feed.__end)
            else:
                self.__sinks.append(feed_queue.put_nowait)

        if attach_lazy:
            initializer_fn = initializer
        else:
            initializer()
            initializer_fn = None

        feed = Feed(Feed.__private, transform(iter(feed_queue.get, Feed.__end)), initializer_fn)
        return feed, feed._run

    def map(self, fn, **kwargs):
        return self._sink(partial(map, fn), **kwargs)

    def filter(self, fn, **kwargs):
        return self._sink(partial(filter, fn), **kwargs)

    def fold(self, fn, acc, **kwargs):
        """Returns an `MVar` that tracks an accumulation of this feed.

        Args:
            fn (Function): An accumulating function that takes a feed item and the current
                accumulator value at each tick.
            acc: An initial value for the accumulator.

        Returns:
            (MVar, Function): The `MVar` and a function to run the accumulation.

        """
        current_acc = acc
        acc_var = MVar()

        def update(item):
            nonlocal current_acc
            current_acc = fn(item, current_acc)
            acc_var.swap(current_acc)

        _, runner = self._sink(partial(map, update), **kwargs)
        return acc_var, runner

    def subscribe(self, fn, **kwargs):
        """A specialized version of `map` that discards the result feed."""
        _, runner = self.map(fn, **kwargs)
        return runner

    def _run(self):
        """Runs this feed by pulling elements of the iterable.

        NOTE: Do not call this function directly; the static constructor and every transformation
        will return a feed alongside its runner. Simply place the runner on its own thread.

        """
        if self.__initializer is not None:
            self.__initializer()
        for item in self.__iterable:
            for sink in self.__sinks:
                sink(item)
        for sink in self.__sinks:
            sink(Feed.__end)
        self.__done = True


def test_feed_simple():
    """Tests the basic functions of `Feed`."""
    thread_manager = ThreadManager()
    feed, runner = Feed.of(range(1000))
    thread_manager.attach("original", runner, should_terminate=True)

    feed_even, runner = feed.filter(lambda x: x % 2 == 0, attach_lazy=False)
    thread_manager.attach("filtered", runner, should_terminate=True)

    aggregate, runner = feed_even.fold(lambda item, acc: acc + item, 0, attach_lazy=False)
    thread_manager.attach("aggregate", runner, should_terminate=True)

    feed_even_str, runner = feed_even.map(str, attach_lazy=False)
    thread_manager.attach("filtered-mapped", runner, should_terminate=True)

    results = []
    runner = feed_even_str.subscribe(results.append, attach_lazy=False)
    thread_manager.attach("results", runner, should_terminate=True)

    thread_manager.run()
    assert aggregate.read() == sum(range(0, 1000, 2))
    assert results == [str(i) for i in range(0, 1000, 2)]


def test_feed_lazy():
    """Tests the difference between lazy and live attachment of children feeds.

    TODO: Make this less jank by allowing the runner threads to be explicitly cancelled (this
    requires some thread plumbing). For now the busy waiting strategy should work fine.

    """
    lazy_results = []
    live_results = []

    feed, runner = Feed.of(itertools.count())
    runner_lazy = feed.subscribe(lazy_results.append)
    runner_live = feed.subscribe(live_results.append, attach_lazy=False)

    runner_thread = Thread(target=runner, daemon=True)
    runner_lazy_thread = Thread(target=runner_lazy, daemon=True)
    runner_live_thread = Thread(target=runner_live, daemon=True)

    runner_thread.start()
    runner_live_thread.start()

    while len(live_results) == 0:
        time.sleep(0.01)

    runner_lazy_thread.start()

    while len(lazy_results) == 0:
        time.sleep(0.01)

    assert live_results[0] == 0
    assert lazy_results[0] > live_results[0]


def test_feed_dead():
    """Test lazy attachment to a dead feed and ensure immediate termination.

    TODO: Make this test not hang if it fails.

    """
    feed, runner = Feed.of(range(1))
    runner_thread = Thread(target=runner)
    runner_thread.start()
    runner_thread.join()

    runner = feed.subscribe(lambda: None)
    runner_thread = Thread(target=runner)
    runner_thread.start()
    runner_thread.join()


def test_feed_buffer_size():
    """Test the buffer size parameter on sinks."""
    feed, runner = Feed.of(range(5))
    feed.subscribe(lambda: None, buffer_size=5, attach_lazy=False)

    def feed_runner():
        try:
            runner()
        except Full:
            return
        raise Exception("expected Full exception")

    thread_manager = ThreadManager()
    thread_manager.attach("feed-runner", feed_runner, should_terminate=True)
    thread_manager.run()
