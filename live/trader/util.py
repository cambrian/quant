from queue import Queue
from threading import Condition, Lock, Thread

import os
import traceback


# A partial implementation of a Haskell MVar (TODO: put/take).
class MVar(object):
    def __init__(self):
        self.__lock = Lock()
        self.__condition = Condition(lock=self.__lock)
        self.__value = None

    def __modify(self, fn):
        self.__lock.acquire()
        self.__value = fn(self.__value)
        self.__condition.notify()
        self.__lock.release()

    def read(self):
        self.__lock.acquire()
        if self.__value is None:
            self.__condition.wait()
        taken_value = self.__value
        self.__value = None
        self.__condition.notify()
        self.__lock.release()
        return taken_value

    # Cannibalizes the MVar to be updated from a feed.
    # The update function should take the existing MVar value and return an update to it based on
    # an incoming piece of data.
    def stream(self, feed, update):
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


# Manages thread lifecycles and links their exceptions to the main thread.
# Arguments are tuples: (name, fn, [True if thread should terminate])
def manage_threads(*threads):
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


class MovingAverage:
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
