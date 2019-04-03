"""Demo of reading logs in programmatically.

Usage (from root): python3 . 2>&1 | python3 scripts/log_btc_usd.py

"""

### SCRIPTS SETUP BLOCK ###
# Needed to run this from outside the directory.
import sys  # isort:skip
import os  # isort:skip

ROOT_DIRECTORY = os.path.join(os.path.dirname(__file__), "..")
sys.path.append(ROOT_DIRECTORY)
### END SCRIPTS SETUP BLOCK ###

from trader.util.constants import BTC_USD
from trader.util.log import Log

BTC_USD_JSON = BTC_USD.json_value()
for entry in Log.stream(sys.stdin, levels={Log.Level.DATA}):
    if entry.message["key"] == "executor-book":
        book = entry.message["value"]
        if tuple(book["pair"]) == BTC_USD_JSON:
            print(book["last_price"])
