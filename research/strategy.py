from abc import ABC, abstractmethod


class Strategy(ABC):
    @abstractmethod
    def step(self, balances, prices):
        '''Should return orders as { btc_usd: size_in_usd, eth_usd: size_in_usd }
        All orders execute at the last trade price (lame i know).'''
        pass


class HoldStrategy(Strategy):
    def step(self, balances, prices):
        return {'btc_usd': 0, 'eth_usd': 0}
