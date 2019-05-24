from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine

import research.util.credentials as creds


def prepare_test_data(exchange, pairs, begin_time, end_time, tick_size_in_min):
    """
    prepare_test_data('binance', ['BTC-USDT', 'ETH-USDT'], '2017-08-18 08:00:00, '2017-08-20 09:00:00', 5)
    returns a `DataFrame` of the form

    timestamp                                    pv
    2017-08-18 08:00:00+00:00                    pv_1
    2017-08-18 08:05:00+00:00                    pv_2
    2017-08-18 08:10:00+00:00                    pv_3
    ...

    where each `pv_i` is a `DataFrame` of the form

      timestamp                  pair      price     volume
    0 2017-08-18 08:00:00+00:00  BTC-USDT  4291.100  2.605985
    1 2017-08-18 08:00:00+00:00  ETH-USDT   307.494  8.248910

    with pricing data fetched from the `binance` table in Postgres.

    TODO: Extend to multiple exchanges.
    """
    pg_uri = "postgresql+psycopg2://{}:{}@{}:{}/{}".format(
        creds.PG_USERNAME,
        quote_plus(creds.PG_PASSWORD),
        creds.PG_HOST,
        creds.PG_PORT,
        creds.PG_DBNAME,
    )
    engine = create_engine(pg_uri)

    query = """
        SELECT
            TO_TIMESTAMP(
                FLOOR(
                    EXTRACT(EPOCH FROM "timestamp") / (60 * {tick_size})
                ) * 60 * {tick_size}
            ) AS tick_begin,
            pair,
            AVG("open")   AS price,
            SUM("volume") AS volume
        FROM {exchange}
        WHERE
            timestamp >= '{begin_time}' AND
            timestamp <= '{end_time}' AND
            pair IN ({pairs})
        GROUP BY tick_begin, pair
        HAVING COUNT(*) = {tick_size}
    """.format(
        exchange=exchange,
        tick_size=tick_size_in_min,
        begin_time=begin_time,
        end_time=end_time,
        pairs=", ".join(["'{}'".format(pair) for pair in pairs]),
    )

    raw_df = pd.read_sql(query, con=engine).rename({"tick_begin": "timestamp"}, axis=1)
    grouped_df = pd.DataFrame(raw_df.groupby("timestamp"))
    grouped_df.columns = ["timestamp", "pv"]
    grouped_df.set_index("timestamp", inplace=True)
    return grouped_df


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
    from research.util.optimizer import BasicGridSearch, optimize, aggregator
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
                ex.tick_fairs(fairs)
                return_value.append((ticks, dummy_exchange.balances, fairs))
                ticks += 1

        thread_manager.attach("main", main, should_terminate=True)
        thread_manager.run()
        return return_value


    param_spaces = {"strategy": [Kalman], "executor": [Executor], "window_size": range(90, 91, 1), "movement_half_life": range(90, 91, 1), "trend_half_life": range(3000, 3001, 1),
    "cointegration_period": range(60, 61, 1), "maxlag": range(120, 121, 1)}
    # param_spaces = {"a": range(-100, 100, 1), "b": range(-50, 50, 1)}
    aggregator(sc, inside_job, param_spaces, parallelism=2)
    # return optimize(sc, BasicGridSearch, inside_job, param_spaces, parallelism=2)


# thread_manager = ThreadManager()
