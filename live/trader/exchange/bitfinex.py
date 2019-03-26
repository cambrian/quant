from trader.exchange.base import Exchange
from trader.util.constants import BITFINEX

from bitfinex import ClientV1, WssClient

import os


class Bitfinex(Exchange):
    """The Bitfinex exchange.

    Store your API key and secret in the `BITFINEX_API_KEY` and `BITFINEX_SECRET` environment
    variables.

    """

    def __init__(self):
        super().__init__()
        self.bfx = ClientV1(os.getenv('BITFINEX_API_KEY', ''),
                            os.getenv('BITFINEX_SECRET', ''))
        self.ws_client = WssClient(os.getenv('BITFINEX_API_KEY', ''),
                                   os.getenv('BITFINEX_SECRET', ''))
        self.ws_client.authenticate(lambda x: None)
        self.ws_client.daemon = True

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
        payload = {
            "request": "/v1/order/new",
            "nonce": self.bfx._nonce(),
            "symbol": pair,
            "amount": volume,
            "price": price,
            "exchange": "bitfinex",
            "side": side,
            "type": order_type,
            "is_postonly": maker
        }
        return self.bfx._post("/order/new", payload=payload, verify=True)

    def cancel_order(self, order_id):
        return self.bfx.delete_order(order_id)

    def get_balance(self):
        return self.bfx.balances()

    def get_open_positions(self):
        return self.bfx.active_orders()
