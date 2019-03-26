from trader.exchange import Exchanges
from trader.util.constants import BITFINEX, BTC_USD
from trader.util.thread import Beat, ThreadManager

import trader.executor as executor
import trader.strategy as strategy

bitfinex = Exchanges.get(BITFINEX)
dummy_strategy = strategy.Dummy()
dummy_executor = executor.Dummy()


def main():
    beat = Beat(60000)
    while beat.loop():
        bitfinex_data = bitfinex.prices(BTC_USD)
        fairs = dummy_strategy.tick(bitfinex_data)
        dummy_executor.tick(fairs)


thread_manager = ThreadManager()
thread_manager.attach('main', main)
thread_manager.run()
