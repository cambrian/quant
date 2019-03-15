from abc import ABC, abstractmethod


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

    @property
    def value(self):
        return self.__value

    def step(self, value):
        if self.__value is None:
            self.__value = value
        self.__value = self.__a * self.__value + (1-self.__a) * value
