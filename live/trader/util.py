from queue import Queue
from threading import Condition, Lock, Thread

import os
import traceback


class MovingAverage:
    """An exponential moving average.

    Attributes:
        half_life (float): The half life of samples passed to `step`.

    """

    def __init__(self, half_life):
        self.__a = 0.5 ** (1 / half_life)
        self.__value = None
        self.__samples_needed = half_life

    @property
    def value(self):
        return self.__value

    def step(self, value):
        if self.__value is None:
            self.__value = value
        self.__value = self.__a * self.__value + (1-self.__a) * value
        self.__samples_needed = max(0, self.__samples_needed - 1)

    @property
    def ready(self):
        return self.__samples_needed == 0


class MVar(object):
    """A partial implementation of a Haskell MVar.

    Notably, several of the usual functions (take/swap/read) are missing, but the general concept
    (of a shared memory location for threads) is the same.

    """

    def __init__(self):
        self.__lock = Lock()
        self.__condition = Condition(lock=self.__lock)
        self.__changed = False
        self.__value = None

    def __modify(self, fn):
        self.__lock.acquire()
        self.__value = fn(self.__value)
        self.__condition.notify()
        self.__lock.release()

    def read_on_write(self):
        """Waits for the MVar to be written to, then reads its value non-destructively.

        Returns:
            The read value.

        """
        self.__lock.acquire()
        if self.__changed == False:
            self.__condition.wait()
        read_value = self.__value
        self.__condition.notify()
        self.__lock.release()
        return read_value

    def stream(self, feed, update):
        """Cannibalizes the MVar to be updated from a feed.

        Args:
            feed (Observable): An observable of some element type.
            update (Function): A function that takes an existing value of this MVar and an element
                of the observable, returning an updated value of the MVar.
        """
        def curried_update(x):
            return lambda current: update(current, x)
        feed.subscribe_(lambda x: self.__modify(curried_update(x)))


# Used to propagate unhandled errors to the main thread.
def _propagate_error(fn, name, exc_queue):
    try:
        fn()
        exc_queue.put((name, None))
    except Exception:
        exc_queue.put((name, traceback.format_exc()))


def manage_threads(*threads):
    """Manages thread lifecycles and links their exceptions to the main thread.

    Args:
        threads: Tuples that look like (name, fn to run, [True if thread should terminate]).

    """
    exc_queue = Queue()
    finite_threads = {}
    for thread in threads:
        if len(thread) == 3:
            (name, fn, terminates) = thread
            if terminates:
                finite_threads[name] = True
        else:
            (name, fn) = thread
        thread = Thread(target=lambda: _propagate_error(fn, name, exc_queue))
        # Allows KeyboardInterrupts to kill the whole program.
        thread.daemon = True
        thread.start()
    completed_threads = 0
    while True:
        (name, exc) = exc_queue.get()
        completed_threads += 1
        if name in finite_threads and exc is None:
            print('Thread <{}> terminated.'.format(name))
            if completed_threads == len(threads):
                break
        else:
            print('Thread <{}> terminated unexpectedly!'.format(name))
            if exc is not None:
                print(exc[:-1])
            os._exit(1)
