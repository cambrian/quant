from trader.exchange.base import Exchange
from trader.util.constants import KRAKEN

import krakenex


class Kraken(Exchange):
    """The Kraken exchange."""

    # TODO: Get real Kraken account w/ KYC and money.
    def __init__(self):
        super().__init__()
        self.kraken = krakenex.API()
        # self.kraken.load_key('secret.key')
        self.translate = lambda x: 'X' + \
            x[:x.find('/') + 1] + 'Z' + x[x.find('/') + 1:]

    def _book(self, pair):
        # The name `pair` should be translated from its value in `constants` to an exchange-specific
        # identifier.
        # TODO
        pass

    def prices(self, pairs):
        # The names in `pairs` should be translated from their values in `constants` to
        # exchange-specific identifiers.
        # TODO
        pass

    def add_order(self, pair, side, order_type, price, volume, maker=False):
        pair = self.translate(pair)
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
