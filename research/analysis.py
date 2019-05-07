import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# number of ticks to sum for price movements in risk calculation
RISK_WINDOW = 10


def principal_market_movements(prices):
    """Returns principal vectors for 1-stddev market movements, plus explained variance ratios"""
    # Fit PCA to scaled (mean 0, variance 1) matrix of single-tick price differences
    pca = PCA(n_components=0.97)
    scaler = StandardScaler()
    price_deltas = prices.diff().iloc[1:].rolling(RISK_WINDOW).sum().iloc[RISK_WINDOW:]
    price_deltas_scaled = scaler.fit_transform(price_deltas)
    pca.fit(price_deltas_scaled)
    pcs = pd.DataFrame(scaler.inverse_transform(pca.components_), columns=price_deltas.columns)
    return (pcs, pca.explained_variance_ratio_)


def max_abs_drawdown(pnls):
    """Maximum peak-to-trough distance before a new peak is attained. The usual metric, expressed
    as a fraction of peak value, does not make sense in the infinite-leverage context."""
    mdd = 0
    peak = -np.inf
    for pnl in pnls:
        if pnl > peak:
            peak = pnl
        dd = peak - pnl
        if dd > mdd:
            mdd = dd
    return mdd


def analyze(results, plot=True):
    """Analyzes P/L and various risk metrics for the given run results.
    Plots balances (with P/L) and market risk over time.

    Note: RoRs are per-tick. They are NOT comparable across time scales."""
    # Balance values
    price_data = results["data"].apply(lambda x: x["price"])
    quote_currency = price_data.columns[0].partition("_")[2]
    prices_ = price_data.rename(columns=lambda pair: pair.partition("_")[0])
    prices_[quote_currency] = 1
    balance_values = results["balances"] * prices_

    pnls = balance_values.sum(axis=1)
    pnl = pnls.iloc[-1]

    # Market risk
    (pmms, pmm_weights) = principal_market_movements(price_data)
    balances_ = (
        results["balances"]
        .drop(columns=[quote_currency])
        .rename(columns=lambda c: "{}_{}".format(c, quote_currency))
    )
    component_risks = np.abs(balances_ @ pmms.T)
    risks = component_risks @ pmm_weights

    total_positions = np.abs(balance_values.drop(columns=[quote_currency]).values).sum()

    if plot:
        fig, axs = plt.subplots(1, 2, figsize=(16, 4))
        balance_values.plot(ax=axs[0])
        pd.DataFrame(pnls, columns=["P/L"]).plot(ax=axs[0])
        pd.DataFrame(risks, columns=["Market Risk"]).plot(ax=axs[1])
        axs[1].axhline(0, color="grey")
        plt.show()
        print("Return on maximum market risk: {0}".format(pnl / (risks.values.max() + 1e-10)))
        print("Return on total market risk:   {0}".format(pnl / (risks.values.sum() + 1e-10)))
        print("Return on total positions:     {0}".format(pnl / (total_positions + 1e-10)))
        print("Sharpe ratio:                  {0}".format(pnl / (pnls.std() + 1e-10)))
        print("Final P/L:                     {0}".format(pnl))
        print("Maximum absolute drawdown:     {0}".format(max_abs_drawdown(pnls)))
        print("Maximum market risk:           {0}".format(risks.values.max()))
        print("Final balances:")
        print(results["balances"].iloc[-1])

    return pnl / (risks.values.max() + 1e-10)
