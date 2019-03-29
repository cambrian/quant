import numpy as np
import pandas as pd
from tqdm import tqdm

from trader.util.stats import Gaussian

# Note: Assumes all orders fill at last trade price. Attempting to simulate market-making would
# require combing through book and trade data, which is too much work for us to do at the moment.
QUOTE_CURRENCY = 'USDT'


def tradable_currencies(price_data):
    currencies = [QUOTE_CURRENCY]
    for pair in price_data.columns:
        currencies.append(pair.split('_')[0])
    return currencies


def get_orders(balances, prices, fairs, size, fractional_fee):
    '''Given current balances, prices, and fair estimates, determine which orders to place.
    Assumes all pairs are XXX_USD. `fairs` should be a Gaussian type.'''
    edges = (fairs / prices) - 1

    def subtract_fees_toward_zero(x):
        if abs(x) < fractional_fee:
            return 0
        if x > 0:
            return x - fractional_fee
        return x + fractional_fee

    edges = Gaussian(edges.mean.apply(subtract_fees_toward_zero), edges.covariance)
    balances = balances.drop([QUOTE_CURRENCY]).rename(lambda c: '{}_{}'.format(c, QUOTE_CURRENCY))
    target_balance_values = edges.mean / edges.stddev * size

    proposed_orders = target_balance_values / prices - balances
    good_direction = edges.mean * proposed_orders > 0

    return proposed_orders * good_direction


def execute_orders(fractional_fee, prices, balances, orders):
    for (pair, size) in orders.items():
        currency = pair.partition('_')[0]
        value = size * prices[pair]
        balances[QUOTE_CURRENCY] -= value
        balances[QUOTE_CURRENCY] -= abs(value) * fractional_fee
        balances[currency] += size


def preprocess(data):
    price_data = data.filter(regex=r'close*')
    volume_data = data.filter(regex=r'volume*')

    def get_pair(c):
        # Renames columns from <prefix>_<exchange>_<base>_<quote> to <base>_<quote>
        return '_'.join(c.split('_')[-2:])

    price_data.rename(get_pair, axis=1, inplace=True)
    volume_data.rename(get_pair, axis=1, inplace=True)
    return price_data, volume_data


def run(strategy, data, size=1000, fractional_fee=0):
    # print('Running {} on data:\n{}\n'.format(type(strategy).__name__, data.head()))
    price_data, volume_data = preprocess(data)
    balances = pd.Series(dict.fromkeys(tradable_currencies(price_data), 0.0))
    # print('Starting balances:\n{}\n'.format(balances))
    balances_ = []
    fairs_ = []
    for date in data.index:
        prices = price_data.loc[date]
        volumes = volume_data.loc[date]

        fairs = strategy.step(prices, volumes)
        # print('Fairs for {}:\n{}'.format(date, fairs))
        orders = get_orders(balances, prices, fairs, size, fractional_fee)
        execute_orders(fractional_fee, prices, balances, orders)

        fairs_.append(fairs)
        balances_.append(balances.copy())
    return {
        "price_data": price_data,
        "fairs": pd.DataFrame(fairs_, index=data.index),
        "balances": pd.DataFrame(balances_, index=data.index),
    }
