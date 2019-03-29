import numpy as np
import pandas as pd

from trader.util.stats import Gaussian

# Note: Assumes all orders fill at last trade price. Attempting to simulate market-making would
# require combing through book and trade data, which is too much work for us to do at the moment.


def data_currencies(data):
    quote_currency = data.iloc[0].index[0].partition("_")[2]
    currencies = [quote_currency]
    for pair in data.iloc[0].index:
        currencies.append(pair.partition("_")[0])
    return currencies


def get_orders(balances, prices, fairs, size, fees):
    """Given current balances, prices, and fair estimates, determine which orders to place.
    Assumes all pairs are XXX_USD.
    `fairs` should be a Gaussian type. """
    quote_currency = prices.index[0].partition("_")[2]
    edges = fairs / prices - 1

    def subtract_fees_toward_zero(x):
        if abs(x) < fees:
            return 0
        if x > 0:
            return x - fees
        return x + fees

    edges = Gaussian(edges.mean.apply(subtract_fees_toward_zero), edges.covariance)
    balances = balances.drop([quote_currency]).rename(lambda c: "{}_{}".format(c, quote_currency))
    target_balance_values = edges.mean / edges.stddev * size

    proposed_orders = target_balance_values / prices - balances
    good_direction = edges.mean * proposed_orders > 0

    return proposed_orders * good_direction


def execute_orders(fees, prices, balances, orders):
    for (pair, size) in orders.items():
        currency, quote_currency = pair.split("_")
        value = size * prices[pair]
        balances[quote_currency] -= value
        balances[quote_currency] -= abs(value) * fees
        balances[currency] += size


def run(strategy, data, size=1000, fees=0):
    balances = pd.Series(dict.fromkeys(data_currencies(data), 0.0))
    balances_ = []
    fairs_ = []
    for frame in data:
        fairs = strategy.step(frame)
        orders = get_orders(balances, frame["price"], fairs, size, fees)
        execute_orders(fees, frame["price"], balances, orders)

        fairs_.append(fairs)
        balances_.append(balances.copy())
    return {
        "data": data,
        "fairs": pd.DataFrame(fairs_, index=data.index),
        "balances": pd.DataFrame(balances_, index=data.index),
    }
