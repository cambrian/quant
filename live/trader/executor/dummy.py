from trader.executor.base import Executor


class Dummy(Executor):
    def _tick(self, input):
        ((fair, stddev), data) = input
        close = float(data['close'])
        print('Close: {}, Fair: {}, Stddev: {}'.format(close, fair, stddev))
        if close < fair - stddev:
            print('Buying 1 BTC at {}.'.format(close))
            # self.exchange.add_order('XXBTZUSD', 'buy', 'market', close, 1)
        elif close > fair + stddev:
            print('Selling 1 BTC at {}.'.format(close))
            # self.exchange.add_order('XXBTZUSD', 'sell', 'market', close, 1)
