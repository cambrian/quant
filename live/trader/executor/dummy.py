from trader.executor.base import Executor


class Dummy(Executor):
    def _tick(self, strategy_input):
        if len(strategy_input) > 0:
            (_, _, fair, stddev, ohlcv) = strategy_input[0]
            close = float(ohlcv['close'])
            print('Close: {}, Fair: {}, Stddev: {}'.format(close, fair, stddev))
            if close < fair - stddev:
                print('Buying 1 BTC at {}.'.format(close))
                # self.exchange.add_order('XBT/USD', 'buy', 'market', close, 1)
            elif close > fair + stddev:
                print('Selling 1 BTC at {}.'.format(close))
                # self.exchange.add_order('XBT/USD', 'sell', 'market', close, 1)
