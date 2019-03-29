from functools import partial, reduce
from queue import Queue

from trader.util.thread import MVar


class PrivateError(Exception):
    pass


class Feed:
    """A multicast stream type for Python.

    NOTE: The constructor is private. Use `Feed.of(iterable)` to construct a feed.

    Transformations of a feed (such as `map` or `filter`) return both a result and a function to run
    the transformation on a separate thread.

    TODO: Allow transformations that change the iterable on the same thread. This makes the library
    less mistake-proof, since `feed.map(foo)` might have unexpected behavior if `feed.map_in_place`
    (for example) is called later on.

    """

    # Hacky solution to prevent manual construction.
    __private = object()

    def __init__(self, private, iterable, initializer=None):
        if private != Feed.__private:
            raise PrivateError("constructor is private")
        self.__iterable = iterable
        self.__initializer = initializer
        self.__sinks = []

    @staticmethod
    def of(iterable):
        """Static constructor for Feed.

        Args:
            iterable: An iterable to initialize the feed from.

        Returns:
            (Feed, Function): The feed and a function to run the feed's iterable.

        """
        feed = Feed(Feed.__private, iterable)
        return (feed, feed.run)

    def _sink(self, transform, buffer_size=256):
        """Creates a new feed by transforming the iterable of this feed.

        Prefer calling `map`, `filter`, or any of the other specialized versions of this method.

        Args:
            transform (Function): A function that transforms an iterable into a new iterable.
            buffer_size (int): An argument to bound the size of the sink queue. This is useful when
                you do not want the parent writer feed to outpace the child reader feed.

        Returns:
            (Feed, Function): The transformed result feed and a function to run the transformation.

        """
        feed_queue = Queue(maxsize=buffer_size)
        # Delay attachment to parent for stateless behavior.
        def initializer():
            self.__sinks.append(feed_queue.put_nowait)

        feed = Feed(Feed.__private, transform(iter(feed_queue.get, None)), initializer)
        return feed, feed.run

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

    def run(self):
        """Runs this feed by pulling elements of the iterable.

        NOTE: You should put `run` calls for each feed on separate threads.

        """
        if self.__initializer is not None:
            self.__initializer()
        for item in self.__iterable:
            for sink in self.__sinks:
                sink(item)
