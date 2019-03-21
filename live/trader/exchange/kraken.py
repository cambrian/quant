from trader.exchange.base import Exchange
from trader.constants import KRAKEN

import json
import krakenex
import time
import websocket as ws


class Kraken(Exchange):
    # TODO: Get real Kraken account w/ KYC and money.
    def __init__(self):
        super().__init__()
        self.name = KRAKEN
        self.kraken = krakenex.API()
        # self.kraken.load_key('secret.key')

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
                    yield result
            except Exception as error:
                print('caught error: ' + repr(error))
                time.sleep(3)

    def add_order(self, pair, side, order_type, price, volume):
        self.kraken.query_private('AddOrder', {
            'pair': pair,
            'type': side,
            'ordertype': order_type,
            'price': price,
            'volume': volume
        })

    def cancel_order(self, order_id):
        self.kraken.query_private('CancelOrder', {
            'txid': order_id
        })

    def get_balance(self):
        self.kraken.query_private('Balance')

    def get_open_positions(self):
        self.kraken.query_private('OpenPositions')
