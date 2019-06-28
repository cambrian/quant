from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine

import research.util.credentials as creds


def prepare_test_data(exchange_pairs, begin_time, end_time, tick_size_in_min):
    """
    Pulls test data from Postgres, in the form of a `DataFrame` of `DataFrame`s, for given exchanges
    and trading pairs, time interval, and tick size (over which by-the-minute trading data is
    aggregated by averaging prices and summing volumes). Fails for exchanges not present in DB,
    but silently ignores pairs with no trading data for corresponding exchange.

    prepare_test_data(
        {
            'binance': ['BTC/USDT', 'ETH/USDT'],
            'bitfinex': ['BTC/USD'],
        },
        '2017-08-18 08:00:00',
        '2017-08-20 09:00:00',
        5
    )
    returns a `DataFrame` of the form

    timestamp                                    pv
    2017-08-18 08:00:00+00:00                    pv_1
    2017-08-18 08:05:00+00:00                    pv_2
    2017-08-18 08:10:00+00:00                    pv_3
    ...

    where each `pv_i` is a `DataFrame` of the form

      timestamp                  pair              price     volume
    0 2017-08-18 08:00:00+00:00  binance-BTC-USDT  4291.100  2.605985
    1 2017-08-18 08:00:00+00:00  binance-ETH-USDT   307.494  8.248910
    2 2017-08-18 08:00:00+00:00  bitfinex-BTC-USD  4302.242  0.421329
    """
    pg_uri = "postgresql+psycopg2://{}:{}@{}:{}/{}".format(
        creds.PG_USERNAME,
        quote_plus(creds.PG_PASSWORD),
        creds.PG_HOST,
        creds.PG_PORT,
        creds.PG_DBNAME,
    )
    engine = create_engine(pg_uri)

    raw_test_data = pd.DataFrame()
    for exchange in exchange_pairs:
        pairs = [p.replace("/", "-") for p in exchange_pairs[exchange]]
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
            pairs=", ".join(["'{}'".format(p) for p in pairs]),
        )

        raw_df = pd.read_sql(query, con=engine).rename({"tick_begin": "timestamp"}, axis=1)
        # Prepend name of exchange to trading pair
        raw_df["pair"] = exchange + "-" + raw_df["pair"]
        raw_test_data = pd.concat([raw_test_data, raw_df])

    # Transform DataFrame into df of dfs, indexed by timestamp
    test_data = pd.DataFrame(raw_test_data.groupby("timestamp"))
    test_data.columns = ["timestamp", "pv"]
    test_data.set_index("timestamp", inplace=True)
    return test_data


# td = prepare_test_data(
#     {"binance": ["BTC/USDT", "ETH/USDT", "dsfj/dgs"], "bitfinex": ["BTC/USD", "ETH/USD"]},
#     "2019-05-06 13:09:00",
#     "2019-05-06 13:16:00",
#     5,
# )
# print(td.head())
# print(td.iloc[0]["pv"])
# print(td.iloc[-1]["pv"])


def backtest_spark_job(sc, input_path, working_dir):
    """
    Your entire job must go within the function definition (including imports).

    TODO: integrate with prepare_test_data to pull from DB instead of HDF from disk
    """
    from trader.exchange import DummyExchange
    from trader.util.constants import BTC_USDT, ETH_USDT, XRP_USDT, BTC, ETH, XRP, BINANCE
    from trader.util.thread import ThreadManager
    from research.util.optimizer import BasicGridSearch, aggregate
    from trader.util.gaussian import Gaussian
    from trader.strategy import Kalman
    from trader.executor import Executor
    from trader.execution_strategy import ExecutionStrategy
    from trader.signal_aggregator import SignalAggregator

    def inside_job(strategy, executor, **kwargs):
        data = pd.read_hdf(input_path).resample("15Min").first().tail(20)
        thread_manager = ThreadManager()
        dummy_exchange = DummyExchange(
            thread_manager, BINANCE, data, {"maker": 0.00075, "taker": 0.00075}
        )
        pairs = [BTC_USDT, ETH_USDT, XRP_USDT]
        execution_strategy = ExecutionStrategy(size=1000, min_edge=0.002, min_edge_to_close=0.0005)
        executor = executor(thread_manager, {dummy_exchange: pairs}, execution_strategy)
        aggregator = SignalAggregator(7500, {"total_market": [BTC, ETH, XRP]})
        strat = strategy(**kwargs)

        fair_history = []
        position_history = []

        def main():
            for row in data:
                if not dummy_exchange.step_time():
                    break
                dummy_data = dummy_exchange.frame(pairs)
                signals = aggregator.step(dummy_data)
                kalman_fairs = strat.tick(dummy_data, signals)
                fairs = kalman_fairs & Gaussian(
                    dummy_data["price"], [1e100 for _ in dummy_data["price"]]
                )
                executor.tick_fairs(fairs)
                fair_history.append(fairs)
                position_history.append(dummy_exchange.positions.copy())

        thread_manager.attach("main", main, should_terminate=True)
        thread_manager.run()
        return {
            "data": data,
            "fairs": pd.DataFrame(fair_history, index=data.index),
            # Should be called 'positions' but analysis.py must also change
            "balances": pd.DataFrame(position_history, index=data.index),
        }

    param_spaces = {
        "strategy": [Kalman],
        "executor": [Executor],
        "window_size": range(90, 91, 1),
        "movement_half_life": range(90, 91, 1),
        "trend_half_life": range(3000, 3001, 1),
        "cointegration_period": range(60, 61, 1),
        "maxlag": range(120, 121, 1),
    }
    return aggregate(sc, inside_job, param_spaces, parallelism=2)


def backtest():
    # NOTE: Keep me at the top. (Sets up the module environment to run this script.)
    import scripts.setup  # isort:skip, pylint: disable=import-error

    import os
    import sys
    from importlib.machinery import SourceFileLoader

    from pyspark import SparkContext

    # Assumes you have JDK 1.8 as installed in the setup script.
    os.environ["PYSPARK_PYTHON"] = "python3"
    os.environ["JAVA_HOME"] = "/Library/Java/JavaVirtualMachines/adoptopenjdk-8.jdk/Contents/Home"

    job = backtest_spark_job

    # Run the job locally.
    sc = SparkContext("local", "backtest")
    value = job(sc, "research/data/1min.h5", os.getcwd())
    sc.stop()

    return value


def analyze_spark_job(sc, results):
    """
    Your entire job must go within the function definition (including imports).
    """
    from research.util.optimizer import aggregate

    def inside_job():
        from research.analysis import analyze

        return analyze(results, plot=False, backtest=True)

    param_spaces = {}
    return aggregate(sc, inside_job, param_spaces, parallelism=2)


def analyze(results):
    # NOTE: Keep me at the top. (Sets up the module environment to run this script.)
    import scripts.setup  # isort:skip, pylint: disable=import-error

    import os
    import sys
    from importlib.machinery import SourceFileLoader

    from pyspark import SparkContext

    # Assumes you have JDK 1.8 as installed in the setup script.
    os.environ["PYSPARK_PYTHON"] = "python3"
    os.environ["JAVA_HOME"] = "/Library/Java/JavaVirtualMachines/adoptopenjdk-8.jdk/Contents/Home"

    job = analyze_spark_job

    # Run the job locally.
    sc = SparkContext("local", "backtest")
    value = job(sc, results)
    sc.stop()

    return value


results = backtest()[0]
price_data = results["data"].apply(lambda x: x["price"])
for row in price_data.columns:
    if row.base not in results["balances"]:
        results["balances"][row.base] = 0.0
print(analyze(results))
