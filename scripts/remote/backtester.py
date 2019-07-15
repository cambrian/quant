def job(sc, input_path, working_dir):
    """Your entire job must go within the function definition (including imports)."""
    import numpy as np
    import pandas as pd
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    from sqlalchemy import create_engine

    import research.util.credentials as creds
    from research.util.optimizer import BasicGridSearch, aggregate, process_aggregate
    from trader.exchange import DummyExchange
    from trader.execution_strategy import ExecutionStrategy
    from trader.executor import Executor
    from trader.signal_aggregator import SignalAggregator
    from trader.strategy import Kalman
    from trader.util.constants import (
        BINANCE,
        BTC,
        BTC_USDT,
        EOS_USDT,
        ETH,
        ETH_USDT,
        LTC_USDT,
        NEO_USDT,
        XRP,
        XRP_USDT,
    )
    from trader.util.gaussian import Gaussian
    from trader.util.thread import ThreadManager

    def backtest_spark_job(input_path, sc):
        """
        Your entire job must go within the function definition (including imports).

        TODO: integrate with prepare_test_data to pull from DB instead of HDF from disk
        """

        def inside_job(strategy, executor, window_size, **kwargs):
            data = pd.read_hdf(input_path)  # .resample("15Min").first()
            warmup_data = data.iloc[:window_size]
            data = data.iloc[window_size:]
            thread_manager = ThreadManager()
            dummy_exchange = DummyExchange(
                thread_manager, BINANCE, data, {"maker": 0.00075, "taker": 0.00075}
            )
            pairs = [BTC_USDT, ETH_USDT, XRP_USDT, LTC_USDT, NEO_USDT, EOS_USDT]
            execution_strategy = ExecutionStrategy(10, 192, 1, 3, -0.5, 0.002, 0.0005, warmup_data)
            executor = executor(thread_manager, {dummy_exchange: pairs}, execution_strategy)
            aggregator = SignalAggregator(window_size, {"total_market": [p.base for p in pairs]})
            warmup_signals = warmup_data.apply(aggregator.step, axis=1)
            strat = strategy(
                window_size=window_size,
                **kwargs,
                warmup_signals=warmup_signals,
                warmup_data=warmup_data
            )

            fair_history = []
            position_history = []

            def main():
                for row in data.iterrows():
                    if not dummy_exchange.step_time():
                        break
                    dummy_data = dummy_exchange.frame(pairs)
                    signals = aggregator.step(dummy_data)
                    kalman_fairs = strat.tick(dummy_data, signals)
                    fairs = kalman_fairs & Gaussian(
                        dummy_data.xs("price", level=1),
                        [1e100 for _ in dummy_data.xs("price", level=1).index],
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
                "params": kwargs,
            }

        param_spaces = {
            "strategy": [Kalman],
            "executor": [Executor],
            "window_size": [500],  # range(50, 52, 1),
            "movement_hl": [90],  # range(6, 7, 1),
            "trend_hl": [3000],  # range(256, 257, 1),
            "mse_hl": [1440],  # range(192, 193, 1),
            "cointegration_period": [50],  # range(32, 33, 1),
            "maxlag": [120],  # range(8, 9, 1),
        }
        return aggregate(sc, inside_job, param_spaces, parallelism=2)

    def analyze_spark_job(sc, results):
        """
        Your entire job must go within the function definition (including imports).
        """

        def principal_market_movements(prices):
            """Returns principal vectors for 1-stddev market movements, plus explained variance ratios"""
            # Fit PCA to scaled (mean 0, variance 1) matrix of single-tick price differences
            pca = PCA(n_components=0.97)
            RISK_WINDOW = 10
            scaler = StandardScaler()
            price_deltas = prices.diff().iloc[1:].rolling(RISK_WINDOW).sum().iloc[RISK_WINDOW:]
            price_deltas_scaled = scaler.fit_transform(price_deltas)
            pca.fit(price_deltas_scaled)
            pcs = pd.DataFrame(
                scaler.inverse_transform(pca.components_), columns=price_deltas.columns
            )
            return (pcs, pca.explained_variance_ratio_)

        def max_abs_drawdown(pnls):
            """Maximum peak-to-trough distance before a new peak is attained. The usual metric, expressed
            as a fraction of peak value, does not make sense in the infinite-leverage context."""
            max_drawdown = 0
            peak = -np.inf
            for pnl in pnls:
                if pnl > peak:
                    peak = pnl
                drawdown = peak - pnl
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            return max_drawdown

        def inside_job(results):
            import numpy as np

            """Analyzes P/L and various risk metrics for the given run results.

            Note: RoRs are per-tick. They are NOT comparable across time scales."""
            # Balance values
            price_data = results["data"].xs("price", axis=1, level=1)
            quote_currency = price_data.columns[0].quote
            prices_ = price_data.rename(columns=lambda pair: pair.base)
            prices_[quote_currency] = 1
            balance_values = results["balances"] * prices_

            pnls = balance_values.sum(axis=1)
            pnl = pnls.iloc[-1]

            # Market risk
            (pmms, pmm_weights) = principal_market_movements(price_data)
            for row in price_data.columns:
                if row not in results["balances"]:
                    results["balances"][row] = 0.0

            balances_ = results["balances"][[pair.base for pair in price_data.columns]].set_axis(
                price_data.columns, axis=1, inplace=False
            )
            component_risks = np.abs(balances_ @ pmms.T)
            risks = component_risks @ pmm_weights

            total_positions = np.abs(balance_values.drop(columns=[quote_currency]).values).sum()
            max_drawdown = max_abs_drawdown(pnls)

            return {
                "params": results["params"],
                "balances_usd": results["balances"].iloc[-1],
                "pnl": pnl,
                "max_market_risk": risks.values.max(),
                "max_drawdown": max_drawdown,
                "return_on_max_market_risk": pnl / (risks.values.max() + 1e-10),
                "return_on_max_drawdown": pnl / (max_drawdown + 1e-10),
                "return_on_total_position": pnl / (total_positions + 1e-10),
                "sharpe_ratio": pnl / (pnls.std() + 1e-10),
            }

        param_spaces = {}
        return process_aggregate(sc, inside_job, param_spaces, parallelism=2, results=results)

    results = backtest_spark_job("/home/hadoop/quant/research/data/1min.h5", sc)
    for attempt in results:
        price_data = attempt["data"].xs("price", axis=1, level=1)
        for row in price_data.columns:
            if row.base not in attempt["balances"]:
                attempt["balances"][row.base] = 0.0
    return analyze_spark_job(sc, results)
