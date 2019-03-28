from functools import partial, reduce
from queue import Queue

from trader.util.thread import MVar


class Feed:
    """A multicast stream type for Python.

    Transformations of a feed (such as `map` or `filter`) return both a result and a function to run
    the transformation on a separate thread.

    TODO: Allow transformations that change the iterable on the same thread. This makes the library
    less mistake-proof, since `feed.map(foo)` might have unexpected behavior if `feed.map_in_place`
    (for example) is called later on.

    Args:
        iterable: An iterable to initialize the feed from.
        initializer (Function): An initializer to run when the feed thread is started. NOTE: You
            should NOT use this parameter.

    """

    def __init__(self, iterable, initializer=None):
        self.__iterable = iterable
        self.__initializer = initializer
        self.__sinks = []

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

        feed = Feed(transform(iter(feed_queue.get, None)), initializer)
        return feed, feed.run

    def map(self, fn, **kwargs):
        return self._sink(partial(map, fn), **kwargs)

    def filter(self, fn, **kwargs):
        return self._sink(partial(filter, fn), **kwargs)

    def fold(self, fn, acc, acc_var=None, **kwargs):
        """Returns an `MVar` that tracks an accumulation of this feed.

        Args:
            fn (Function): An accumulating function that takes a feed item and the current
                accumulator value at each tick.
            acc: An initial value for the accumulator.
            acc_var: An optional argument to provide your own pre-existing `MVar`. This is useful in
                certain scenarios, such as folding many feeds into a single `MVar`.

        Returns:
            (MVar, Function): The `MVar` and a function to run the accumulation.

        """
        current_acc = acc
        if acc_var is None:
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
