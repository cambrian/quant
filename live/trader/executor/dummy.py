from trader.executor.base import Executor
from trader.constants import BITFINEX
from trader.exchange import exchanges


class Dummy(Executor):
    def _tick(self, strategy_input):
        if len(strategy_input) > 0:
            (_, _, fair, stddev, ohlcv) = strategy_input[0]
            close = float(ohlcv['close'])
            print('Close: {}, Fair: {}, Stddev: {}'.format(close, fair, stddev))
            if close < fair - stddev:
                print('Buying 0.0001 BTC at {}.'.format(close))
                # print(exchanges[BITFINEX].add_order(
                #     'BTCUSD', 'buy', 'exchange market', ohlcv['close'], "0.004"))
            elif close > fair + stddev:
                print('Selling 0.0001 BTC at {}.'.format(close))
                # print(exchanges[BITFINEX].add_order(
                #     'BTCUSD', 'sell', 'exchange market', ohlcv['close'], "0.004"))
            print(exchanges[BITFINEX].get_balance())
            print(exchanges[BITFINEX].get_open_positions())
