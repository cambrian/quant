from queue import Queue
from threading import Condition, Lock, Thread

import os
import traceback


class MVar:
    """A partial implementation of a Haskell MVar.

    Many of the usual functions (e.g. `put` or `take`) are missing, but the general concept (of a
    shared memory location for threads) is the same.

    """

    def __init__(self):
        self.__lock = Lock()
        self.__condition = Condition(lock=self.__lock)
        self.__changed = False
        self.__value = None

    def swap(self, new_value):
        """Puts a new value in the `MVar` and returns the old value, if any.

        Args:
            new_value: The new value.

        Returns:
            The old value.

        """
        self.__lock.acquire()
        old_value = self.__value
        self.__value = new_value
        self.__condition.notify_all()
        self.__lock.release()
        return old_value

    def read_on_write(self):
        """Reads the current value of the `MVar` when it is written to.

        Returns:
            The current value.

        """
        self.__lock.acquire()
        if self.__changed == False:
            self.__condition.wait()
        read_value = self.__value
        self.__changed = False
        self.__lock.release()
        return read_value


class ThreadManager:
    """A centralized runner for our Python threads.

    Prints useful debug info on failures.

    """

    def __init__(self):
        self.__termination_queue = Queue()
        self.__finite_thread_count = 0
        self.__thread_runners = []

    def __propagate_error(self, name, fn, should_terminate):
        # Used to propagate unhandled errors to the main thread.
        try:
            fn()
            if should_terminate:
                reason = None
            else:
                reason = 'Expected thread to run forever.\n'
            self.__termination_queue.put((name, reason))
        except Exception:
            self.__termination_queue.put((name, traceback.format_exc()))

    def attach(self, name, fn, should_terminate=False):
        """Attaches a function to this thread manager as a new thread to be created.

        Args:
            name (str): A name to identify the new thread.
            fn (Function): A function to run on the new thread.
            should_terminate (bool): Whether we expect this function to terminate (or run forever).

        """
        if should_terminate:
            self.__finite_thread_count += 1

        def runner(): self.__propagate_error(name, fn, should_terminate)
        self.__thread_runners.append(runner)

    def run(self):
        """Cannibalizes the current thread and runs any attached functions as children threads."""
        for runner in self.__thread_runners:
            thread = Thread(target=runner)
            # Force-kill on KeyboardInterrupts.
            thread.daemon = True
            thread.start()
        completed_threads = 0
        while True:
            (name, exc) = self.__termination_queue.get()
            completed_threads += 1
            if exc is None:
                print('Thread <{}> terminated.'.format(name))
                if completed_threads == self.__finite_thread_count:
                    break
            else:
                print('Thread <{}> terminated unexpectedly!'.format(name))
                if exc is not None:
                    print(exc[:-1])
                os._exit(1)
