def job(sc, input_path, working_dir):
    """Your entire job must go within the function definition (including imports)."""
    from backtest import backtest_spark_job, analyze_spark_job

    results = backtest_spark_job("research/data/1min.h5", sc)[0]
    price_data = results["data"].xs("price", axis=1, level=1)
    for row in price_data.columns:
        if row.base not in results["balances"]:
            results["balances"][row.base] = 0.0
    return analyze_spark_job(sc, results)
