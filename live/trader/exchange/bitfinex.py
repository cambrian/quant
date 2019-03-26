from trader.exchange.base import Exchange
from trader.util.constants import BTC_USD, ETH_USD, XRP_USD

from bitfinex import ClientV1, ClientV2, WssClient

import os
import pandas as pd


class Bitfinex(Exchange):
    """The Bitfinex exchange.

    Store your API key and secret in the `BITFINEX_API_KEY` and `BITFINEX_SECRET` environment
    variables.

    """

    def __init__(self):
        super().__init__()
        self.bfxv1 = ClientV1(os.getenv('BITFINEX_API_KEY', ''),
                              os.getenv('BITFINEX_SECRET', ''))
        self.bfxv2 = ClientV2(os.getenv('BITFINEX_API_KEY', ''),
                              os.getenv('BITFINEX_SECRET', ''))
        self.ws_client = WssClient(os.getenv('BITFINEX_API_KEY', ''),
                                   os.getenv('BITFINEX_SECRET', ''))
        self.ws_client.authenticate(lambda x: None)
        self.ws_client.daemon = True
        self.translate = {
            BTC_USD: 'tBTCUSD',
            ETH_USD: 'tETHUSD',
            XRP_USD: 'tXRPUSD'
        }

    def _book(self, pair):
        # The name `pair` should be translated from its value in `constants` to an exchange-specific
        # identifier.
        # TODO
        pass

    # time_frame expected as string rep: '1m', '5m', '1h', etc.
    def prices(self, pairs, time_frame):
        data = {
            'Close': [],
            'Volume': []
        }
        for pair in pairs:
            pair = self.translate[pair]
            # Ignore index [0] timestamp
            ochlv = self.bfxv2.candles(time_frame, pair, "last")[1:]
            data['Close'].append(ochlv[1])
            data['Volume'].append(ochlv[4])
        return pd.DataFrame.from_dict(data, orient='index', columns=pairs)

    def add_order(self, pair, side, order_type, price, volume, maker=False):
        payload = {
            "request": "/v1/order/new",
            "nonce": self.bfxv1._nonce(),
            "symbol": pair,
            "amount": volume,
            "price": price,
            "exchange": "bitfinex",
            "side": side,
            "type": order_type,
            "is_postonly": maker
        }
        return self.bfxv1._post("/order/new", payload=payload, verify=True)

    def cancel_order(self, order_id):
        return self.bfxv1.delete_order(order_id)

    def get_balance(self):
        return self.bfxv1.balances()

    def get_open_positions(self):
        return self.bfxv1.active_orders()
