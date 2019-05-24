import pandas as pd

# class BackTest:
#     def __init__(self, _strategy, _execution_model, _data, _params):
#         self.strategy = _strategy
#         self.execution_model = _execution_model
#         self.data = _data
#         self.params = _params


# #             executor.tick_fairs(fairs)
# #         def foo():

# #         # Test output
# #         def bar():
# #         param_spaces = {}
# #         return bar(sc, foo, param_spaces)

# backtester = None
# def backtest(strategy, execution_model, data, params):
#     backtester = BackTest(strategy, execution_model, data, params)

def job(sc, input_path, working_dir):
    """Your entire job must go within the function definition (including imports)."""
    from trader.exchange import DummyExchange
    from trader.util.constants import BTC_USDT, ETH_USDT
    from trader.util.thread import ThreadManager
    from research.util.optimizer import BasicGridSearch, optimize
    from trader.util.gaussian import Gaussian
    from trader.strategy import Kalman
    from trader.executor import Executor


    def inside_job(strategy, executor, **kwargs):
        data = pd.read_hdf(input_path)
        thread_manager = ThreadManager()
        dummy_exchange = DummyExchange(thread_manager, data, {})
        print(executor)
        ex = executor(thread_manager, {dummy_exchange: [BTC_USDT, ETH_USDT]}, size=100, min_edge=0.0005)
        strat = strategy(**kwargs)

        return_value = []
        def main():
            ticks = 0
            for row in data[:100]:
                dummy_exchange.step_time()
                dummy_data = dummy_exchange.prices([BTC_USDT, ETH_USDT], '1m')
                kalman_fairs = strat.tick(dummy_data)
                fairs = kalman_fairs & Gaussian(dummy_data['price'], [1e100 for _ in dummy_data['price']])
                print(fairs)
                ex.tick_fairs(fairs)
                return_value.append((ticks, dummy_exchange.balances, fairs))
                ticks += 1

        thread_manager.attach("main", main, should_terminate=True)
        thread_manager.run()
        return return_value


    param_spaces = {"strategy": [Kalman], "executor": [Executor], "window_size": range(90, 92, 1), "movement_half_life": range(90, 92, 1), "trend_half_life": range(3000, 3002, 1),
    "cointegration_period": range(60, 62, 1), "maxlag": range(120, 122, 1)}
    # param_spaces = {"a": range(-100, 100, 1), "b": range(-50, 50, 1)}
    return optimize(sc, BasicGridSearch, inside_job, param_spaces, parallelism=2)


# thread_manager = ThreadManager()
