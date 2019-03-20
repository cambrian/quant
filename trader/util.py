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

    def __swap(self, value):
        self.__lock.acquire()
        current_value = self.__value
        self.__value = value
        self.__condition.notify()
        self.__lock.release()
        return current_value

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
    def stream(self, feed):
        feed.subscribe_(self.__swap)


# Used to propagate unhandled errors to the main thread.
def _propagate_error(fn, name, queue):
    try:
        fn()
        queue.put((name, None))
    except Exception:
        queue.put((name, traceback.format_exc()))


# Manages several threads and links their exceptions to the main thread.
def run_threads_forever(*fns):
    exc_queue = Queue()
    threads = []
    for (name, fn) in fns:
        thread = Thread(target=lambda: _propagate_error(fn, name, exc_queue))
        # Allows KeyboardInterrupts to kill the whole program.
        thread.daemon = True
        threads.append(thread)
        thread.start()
    (name, exc) = exc_queue.get()
    print('Thread <{}> terminated.'.format(name))
    if exc is not None:
        print(exc[:-1])
    os._exit(0)
