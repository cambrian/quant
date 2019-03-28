import numpy as np
import pandas as pd

from trader.util.stats import Gaussian

# Note: Assumes all orders fill at last trade price. Attempting to simulate market-making would
# require combing through book and trade data, which is too much work for us to do at the moment.


def data_currencies(data):
    currencies = ['usd']
    for pair in data['prices'].columns:
        currencies.append(pair.partition('_')[0])
    return currencies


def get_orders(balances, prices, fairs, size, fees):
    '''Given current balances, prices, and fair estimates, determine which orders to place.
    Assumes all pairs are XXX_USD.
    `fairs` should be a Gaussian type. '''
    edges = (fairs / prices) - 1

    def subtract_fees_toward_zero(x):
        if abs(x) < fees:
            return 0
        if x > 0:
            return x - fees
        return x + fees
    edges = Gaussian(edges.mean.apply(subtract_fees_toward_zero), edges.covariance)
    balances = balances.drop(['usd']).rename(lambda c: c + '_usd')
    target_balance_values = edges.mean / edges.stddev * size

    proposed_orders = (target_balance_values / prices - balances)
    good_direction = edges.mean * proposed_orders > 0

    return proposed_orders * good_direction


def execute_orders(fees, prices, balances, orders):
    for (pair, size) in orders.items():
        currency = pair.partition("_")[0]
        value = size * prices[pair]
        balances['usd'] -= value
        balances['usd'] -= abs(value) * fees
        balances[currency] += size


def run(strategy, data, size=1000, fees=0):
    balances = pd.Series(dict.fromkeys(data_currencies(data), 0.))
    balances_ = []
    fairs_ = []
    index = data['prices'].index
    for (date, prices) in data['prices'].iterrows():
        volumes = data['volumes'].loc[date]

        fairs = strategy.step(prices, volumes)
        orders = get_orders(balances, prices, fairs, size, fees)
        execute_orders(fees, prices, balances, orders)

        fairs_.append(fairs)
        balances_.append(balances.copy())
    return {
        'data': data,
        'fairs': pd.DataFrame(fairs_, index=index),
        'balances': pd.DataFrame(balances_, index=index)
    }
