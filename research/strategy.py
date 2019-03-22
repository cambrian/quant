from abc import ABC, abstractmethod
from math import sqrt


class Strategy(ABC):
    @abstractmethod
    def step(self, balances, prices, volumes):
        '''Should return orders as { <pair>: size_in_base_currency }
        All orders execute at the last trade price (lame i know).'''
        pass


class HoldStrategy(Strategy):
    def step(self, balances, prices, volumes):
        return {}


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


class Gaussian:
    def __init__(self, mean, variance):
        self.mean = mean
        self.variance = variance

    @property
    def stddev(self):
        return sqrt(self.stddev)

    def __add__(self, x):
        return Gaussian(self.mean + x.mean, self.variance + x.variance)

    def __mul__(self, scalar):
        return Gaussian(self.mean * scalar, self.variance * scalar * scalar)

    def __sub__(self, x):
        return self + -x

    def __div__(self, scalar):
        return self * (1/scalar)
