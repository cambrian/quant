from trader.exchange import Exchanges
from trader.executor.base import Executor
from trader.util.constants import BITFINEX

from operator import itemgetter

import trader.strategy as strategy


class Dummy(Executor):
    """A shitty executor for testing purposes."""

    def expected_strategy_feeds(self):
        return {
            strategy.Dummy
        }

    def _tick(self, strategy_inputs):
        dummy_inputs = strategy_inputs[strategy.Dummy]
        if BITFINEX in dummy_inputs and 'BTCUSD' in dummy_inputs[BITFINEX]:
            bitfinex = Exchanges.get(BITFINEX)
            data = dummy_inputs[BITFINEX]['BTCUSD']
            ohlcv, fair_price, std_dev = itemgetter(
                'ohlcv', 'fair_price', 'std_dev')(data)
            close = float(ohlcv['close'])
            print('Close: {}, Fair: {}, Std: {}'.format(
                close, fair_price, std_dev))
            if close < fair_price - std_dev:
                print('Buying 0.0001 BTC at {}.'.format(close))
                # print(bitfinex.add_order('BTCUSD', 'buy',
                #                          'exchange market', ohlcv['close'], '0.004'))
            elif close > fair_price + std_dev:
                print('Selling 0.0001 BTC at {}.'.format(close))
                # print(bitfinex.add_order('BTCUSD', 'sell',
                #                          'exchange market', ohlcv['close'], '0.004'))
            print(bitfinex.get_balance())
            print(bitfinex.get_open_positions())
