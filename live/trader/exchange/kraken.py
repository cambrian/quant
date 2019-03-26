from trader.exchange.base import Exchange
from trader.util.constants import KRAKEN

from datetime import datetime

import json
import krakenex
import time
import websocket as ws


class Kraken(Exchange):
    """The Kraken exchange."""

    # TODO: Get real Kraken account w/ KYC and money.
    def __init__(self):
        super().__init__()
        self.kraken = krakenex.API()
        # self.kraken.load_key('secret.key')
        self.translate = lambda x: 'X' + \
            x[:x.find('/') + 1] + 'Z' + x[x.find('/') + 1:]

    def _feed(self, pair, time_interval):
        for _ in range(3):
            try:
                self.ws = ws.create_connection('wss://ws-sandbox.kraken.com')
            except Exception as error:
                print('caught error: ' + repr(error))
                time.sleep(3)
            else:
                break

        self.ws.send(json.dumps({
            'event': 'subscribe',
            'pair': [pair],
            'subscription': {
                'name': 'ohlc',
                'interval': time_interval
            }
        }))

        while True:
            try:
                result_raw = self.ws.recv()
                # TODO: Error handling of this await.
                result = json.loads(result_raw)
                # Ignore heartbeats.
                if not isinstance(result, dict):
                    ohlcv = {}
                    ohlcv['timestamp'] = datetime.now()
                    ohlcv['open'] = result[1][2]
                    ohlcv['high'] = result[1][3]
                    ohlcv['low'] = result[1][4]
                    ohlcv['close'] = result[1][5]
                    ohlcv['volume'] = result[1][6]
                    yield ohlcv
            except Exception as error:
                print('caught error: ' + repr(error))
                time.sleep(3)

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
