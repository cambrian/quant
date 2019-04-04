"""Demo of reading logs in programmatically.

Usage (from root): python3 . 2>&1 | python3 scripts/log_btc_usd.py

"""

# Setup the module environment to run this script.
import setup  # isort:skip, pylint: disable=import-error

import sys

from trader.util.constants import BTC_USD
from trader.util.log import Log

BTC_USD_JSON = BTC_USD.json_value()
for entry in Log.stream(sys.stdin, levels={Log.Level.DATA}):
    if entry.message["key"] == "executor-book":
        book = entry.message["value"]
        if tuple(book["pair"]) == BTC_USD_JSON:
            print(book["last_price"])
