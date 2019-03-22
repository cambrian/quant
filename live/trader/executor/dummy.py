from trader.executor.base import Executor
from trader.constants import BITFINEX
from trader.exchange import exchanges

from operator import itemgetter


class Dummy(Executor):
    def _tick(self, strategy_inputs):
        print(strategy_inputs)
        if BITFINEX in strategy_inputs and 'BTCUSD' in strategy_inputs[BITFINEX]:
            data = strategy_inputs[BITFINEX]['BTCUSD']
            ohlcv, fair_price, std_dev = itemgetter(
                'ohlcv', 'fair_price', 'std_dev')(data)
            close = float(ohlcv['close'])
            print('Close: {}, Fair: {}, Std: {}'.format(
                close, fair_price, std_dev))
            if close < fair_price - std_dev:
                print('Buying 0.0001 BTC at {}.'.format(close))
                # print(exchanges[BITFINEX].add_order(
                #     'BTCUSD', 'buy', 'exchange market', ohlcv['close'], '0.004'))
            elif close > fair_price + std_dev:
                print('Selling 0.0001 BTC at {}.'.format(close))
                # print(exchanges[BITFINEX].add_order(
                #     'BTCUSD', 'sell', 'exchange market', ohlcv['close'], '0.004'))
            print(exchanges[BITFINEX].get_balance())
            print(exchanges[BITFINEX].get_open_positions())
