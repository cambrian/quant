"""Spark/EMR optimizer tools."""

import os
from abc import ABC, abstractmethod
from itertools import islice, product


def _dict_product(d):
    """Maps `{a: [x, y], b: [z, w]}`
         to `[{a: x, b: z}, {a: x, b: w}, {a: y, b: z}, {a: y, b: w}]`.

    """
    return (dict(zip(d.keys(), vs)) for vs in product(*d.values()))


def _take(n, iterable):
    """Takes the first `n` items of the given iterable."""
    return list(islice(iterable, n))


class ParameterGenerator(ABC):
    """An abstract class for param search optimizers.

    Args:
        param_spaces (Dict): A dictionary from named parameters to the values they can take on. Each
            optimizer can choose to support discrete or continuous parameters as desired.

    """

    @abstractmethod
    def __init__(self, param_spaces, **kwargs):
        pass

    @abstractmethod
    def next_trials(self, last_results=None):
        """Given some feedback `last_results` from the last set of trials, outputs the next set of
        parameter trials.

        Args:
            last_results (Comparable): Results of the last set of trials from this function. Use
                `None` if calling this for the first time.

        Returns:
            list: A list of dicts from named parameters to trial values.

        """
        pass

    @abstractmethod
    def best_params(self):
        """Returns a tuple of (best params, best result) so far (`None` if no trials have run)."""
        pass


class BasicGridSearch(ParameterGenerator):
    def __init__(self, param_spaces, chunk_size=None):
        """Expects `param_spaces` to contain generator expressions for grid values."""
        self.__trials = _dict_product(param_spaces)
        self.__chunk_size = chunk_size
        self.__last_trials = None
        self.__best_params = None
        self.__best_result = None
        self.__done = False

    def next_trials(self, last_results=None):
        # Update the best parameters based on results.
        # Other optimizers might use this to adapt their search.
        if last_results is not None and self.__last_trials is not None:
            for i in range(len(last_results)):
                params = self.__last_trials[i]
                result = last_results[i]

                if self.__best_result is None or result > self.__best_result:
                    self.__best_params = params
                    self.__best_result = result

        if self.__done:
            # Set this to None after results are fed back for the last time.
            self.__last_params = None
            return None

        # Return all trials at once?
        if self.__chunk_size is None:
            trials = list(self.__trials)
            self.__done = True
        # Or chunk?
        else:
            trials = _take(self.__chunk_size, self.__trials)
            if len(trials) < self.__chunk_size:
                self.__done = True

        self.__last_trials = trials
        return trials

    def best_params(self):
        return (self.__best_params, self.__best_result)


def optimize(sc, strategy, runner, param_spaces, parallelism, **kwargs):
    def sim(kwargs):
        return runner(**kwargs)

    optimizer = strategy(param_spaces, **kwargs)
    last_results = None
    while True:
        trials = optimizer.next_trials(last_results)
        if trials is None:
            break
        rdd = sc.parallelize(trials, parallelism)
        last_results = rdd.map(sim).collect()
    return optimizer.best_params()

def aggregate(sc, runner, param_spaces, **kwargs):
    def sim(kwargs):
        return runner(**kwargs)
    rdd = sc.parallelize(_dict_product(param_spaces))
    res = rdd.map(sim).collect()
    print(res)
