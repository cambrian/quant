import csv
import os
import string
import time
from functools import reduce

import ccxt
import pandas as pd

MAX_ATTEMPTS = 5

# Subject to debate/change (currently top 20 highest volume coins on CMC).
GOOD_COINS = [
    "BTC",
    "USD",
    "ETH",
    "LTC",
    "EOS",
    "USDT",
    "XRP",
    "QTUM",
    "NEO",
    "DASH",
    "ZEC",
    "BCH",
    "ETC",
    "BNB",
    "XLM",
    "TRX",
    "ONT",
    "AE",
    "OMG",
    "BSV",
]


class ParamsError(Exception):
    pass


class RetryError(Exception):
    pass


def tick_size_to_ms(exchange, tick_size):
    tick_size_seconds = exchange.parse_timeframe(tick_size)
    return tick_size_seconds * 1000


def retry_fetch_ohlcv(max_retries, exchange, pair, tick_size_ms, position_ms, batch_size):
    for _ in range(max_retries):
        ohlcv = exchange.fetch_ohlcv(pair, tick_size_ms, position_ms, batch_size)
        if ohlcv is not None:
            return ohlcv
    raise RetryError(
        "Failed to fetch {} from {} in {} attempts.".format(pair, exchange, max_retries)
    )


def scrape_ohlcv(max_retries, exchange, pair, tick_size, start_ms, num_ticks, batch_size_max):
    tick_size_ms = tick_size_to_ms(exchange, tick_size)
    position_ms = start_ms
    end = start_ms + num_ticks * tick_size_ms
    print("Batch Size: {}".format(batch_size_max))
    print("Total Entries: {}".format((end - start_ms) // tick_size_ms))
    print("Note: Entries will not exist if they predate exchange history.")
    while True:
        if position_ms >= end:
            break
        batch_size = max(0, min(batch_size_max, (end - position_ms) // tick_size_ms))
        ohlcv = [
            row
            for row in retry_fetch_ohlcv(
                max_retries, exchange, pair, tick_size, position_ms, batch_size
            )
            if row[0] < end
        ]
        if len(ohlcv) == 0:
            print("Warning: Exchange returned zero entries prior to end time. See note?")
            break
        position_ms = ohlcv[-1][0] + tick_size_ms
        if len(ohlcv) < batch_size and position_ms < end:
            print("Warning: Exchange returned fewer rows than expected. Check your batch size?")
        print("Entries Processed: {}".format((position_ms - start_ms) // tick_size_ms))
        yield ohlcv


def write_csv(filename, generator):
    with open(filename, "w+") as f:
        writer = csv.writer(f, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for data in generator:
            writer.writerows(data)


def scrape_ohlcv_to_csv(
    filename, max_retries, exchange, pair, tick_size, start_ms, num_ticks, batch_size_max
):
    try:
        ohlcv_generator = scrape_ohlcv(
            max_retries, exchange, pair, tick_size, start_ms, num_ticks, batch_size_max
        )
        write_csv(filename, ohlcv_generator)
        print("Scraping for {} succeeded.".format(filename))
    except RetryError:
        print("Scraping for {} failed.".format(filename))


def get_data_filename(pair, tick_size, start, num_ticks_str="all"):
    return "{}-{}-{}-{}".format(
        pair.replace("/", "-"), tick_size, start.replace(":", "-"), num_ticks_str
    )


def get_data_directory(data_dir, exchange):
    return "{}/{}".format(data_dir, exchange)


def get_data_path(data_dir, exchange, pair, tick_size, start, num_ticks_str="all"):
    return "{}/{}.csv".format(
        get_data_directory(data_dir, exchange),
        get_data_filename(pair, tick_size, start, num_ticks_str),
    )


def load_data_as_frame(data_dir, exchange, pair, tick_size, start, num_ticks_str="all"):
    path = get_data_path(data_dir, exchange, pair, tick_size, start, num_ticks_str)
    if not os.path.isfile(path):
        print("WARNING: Data for {} on {} does not exist.".format(pair, exchange))
        return None
    df = pd.read_csv(path, index_col=0)
    if df.empty:
        print("WARNING: Empty CSV for {} on {}".format(pair, exchange))
        return None
    df.index = pd.to_datetime(df.index, unit="ms")
    return df


def aggregate_data(data_dir, exchange_pairs, tick_size, start, num_ticks_str="all"):
    """`exchange_pairs` is dict of form `{'binance': ['BTC/ETH', 'XMR/BTC', ...], ...}`"""
    dfs = []
    for exchange in exchange_pairs:
        for pair in exchange_pairs[exchange]:
            df = load_data_as_frame(data_dir, exchange, pair, tick_size, start, num_ticks_str)
            if df is None:
                continue
            df.rename(
                lambda col: "{}_{}_{}".format(col, exchange, pair.replace("/", "_")),
                axis=1,
                inplace=True,
            )
            first_ts, last_ts = df.index[0], df.index[-1]
            print("Loaded pair {} on {} ({} to {})".format(pair, exchange, first_ts, last_ts))
            dfs.append(df)

    return reduce(lambda l, r: pd.merge(l, r, left_index=True, right_index=True, how="outer"), dfs)


def resample_to(timeframe, df):
    ohlcv_dict = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(timeframe).agg(ohlcv_dict)


def populate(data_dir, exchanges, pairs, tick_size, start, num_ticks=None):
    for (exchange_id, batch_size_max) in exchanges:
        exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True})
        exchange.load_markets()
        if not exchange.has["fetchOHLCV"]:
            print("{} does not expose OHLCV data.".format(exchange.id))
            continue
        os.makedirs(get_data_directory(data_dir, exchange_id), exist_ok=True)
        # Validate start time.
        start_ms = exchange.parse8601(start)
        now = exchange.milliseconds()
        if start_ms > now:
            raise ParamsError("Start time in the future for exchange {}.".format(exchange_id))
        # Validate number of ticks.
        tick_size_ms = tick_size_to_ms(exchange, tick_size)
        if num_ticks is None:
            num_ticks = (now - start_ms) // tick_size_ms
            num_ticks_str = "all"
        elif start_ms + num_ticks * tick_size_ms > now:
            print("End time in the future for exchange {}. Clamping ticks.".format(exchange_id))
            num_ticks = (now - start_ms) // tick_size_ms
            num_ticks_str = str(num_ticks)
        else:
            num_ticks_str = str(num_ticks)
        # Scrape each pair for exchange to a separate file.
        for pair in pairs:
            if not pair in exchange.symbols:
                print("Exchange {} does not trade {}.".format(exchange_id, pair))
                continue
            print("Downloading price history for {} on exchange {}.".format(pair, exchange_id))
            path = get_data_path(data_dir, exchange_id, pair, tick_size, start, num_ticks_str)
            scrape_ohlcv_to_csv(
                path, MAX_ATTEMPTS, exchange, pair, tick_size, start_ms, num_ticks, batch_size_max
            )


def grab_all_pairs(data_dir, exchanges, tick_size):
    for (exchange_id, batch_size_max) in exchanges:
        exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True})
        exchange.load_markets()
        good_symbols = list(
            filter(
                lambda x: x.split("/")[0] in GOOD_COINS and x.split("/")[1] in GOOD_COINS,
                exchange.symbols,
            )
        )
        populate(
            data_dir,
            [(exchange_id, batch_size_max)],
            good_symbols,
            tick_size,
            "2000-01-01T00:00:00Z",
        )


if __name__ == "__main__":
    data_dir = "data"
    exchanges = [("binance", 1000), ("bitfinex", 200)]
    grab_all_pairs(data_dir, exchanges, "1m")
