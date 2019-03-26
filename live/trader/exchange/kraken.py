from trader.exchange.base import Exchange
from trader.util.constants import KRAKEN, BTC_USD, ETH_USD, XRP_USD

import krakenex
import pandas as pd


class Kraken(Exchange):
    """The Kraken exchange."""

    def __init__(self):
        super().__init__()
        self.kraken = krakenex.API()
        # self.kraken.load_key('secret.key')
        self.translate = {
            BTC_USD: 'XXBTZUSD',
            ETH_USD: 'XETHZUSD',
            XRP_USD: 'XXRPZUSD'
        }

    def _book(self, pair):
        # The name `pair` should be translated from its value in `constants` to an exchange-specific
        # identifier.
        # TODO
        pass

    # time_frame expected to be integer in minutes
    def prices(self, pairs, time_frame):
        data = {
            'Close': [],
            'Volume': []
        }
        for pair in pairs:
            pair = self.translate[pair]
            params = {
                'pair': pair,
                'timeframe': time_frame
            }
            # Most recent update is second to last element in array - last element is unconfirmed
            # Open, high, low, close, vwap, volume
            ohlcvv = self.kraken.query_public("OHLC", data=params)['result'][pair][-2][1:]
            data['Close'].append(ohlcvv[3])
            data['Volume'].append(ohlcvv[5])
        return pd.DataFrame.from_dict(data, orient='index', columns=pairs)

    def add_order(self, pair, side, order_type, price, volume, maker=False):
        pair = self.translate[pair]
        query = {
            'pair': pair,
            'type': side,
            'ordertype': order_type,
            'price': price,
            'volume': volume
        }
        if maker:
            query['oflags'] = 'post'
        self.kraken.query_private('AddOrder', query)

    def cancel_order(self, order_id):
        self.kraken.query_private('CancelOrder', {
            'txid': order_id
        })

    def get_balance(self):
        self.kraken.query_private('Balance')

    def get_open_positions(self):
        self.kraken.query_private('OpenPositions')
