import ccxt
import time
import csv
import os
import string


MAX_ATTEMPTS = 5


class RetryError(Exception):
    pass


def retry_fetch_ohlcv(max_retries, exchange, symbol, timeframe, since, limit):
    for _ in range(max_retries):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit)
            if ohlcv is not None:
                return ohlcv
        except Exception:
            continue
    raise RetryError('Failed to fetch {} from {} in {} attempts.'
                     .format(symbol, exchange, max_retries))


def scrape_ohlcv(max_retries, exchange, symbol, timeframe, since, limit):
    earliest_timestamp = exchange.milliseconds()
    timeframe_duration_in_seconds = exchange.parse_timeframe(timeframe)
    timeframe_duration_in_ms = timeframe_duration_in_seconds * 1000
    time_delta = limit * timeframe_duration_in_ms
    all_ohlcv = []
    while True:
        fetch_since = earliest_timestamp - time_delta
        ohlcv = retry_fetch_ohlcv(
            max_retries, exchange, symbol, timeframe, fetch_since, limit)
        # If we have reached the beginning of history.
        if ohlcv[0][0] >= earliest_timestamp:
            break
        earliest_timestamp = ohlcv[0][0]
        all_ohlcv = ohlcv + all_ohlcv
        if fetch_since < since:
            break
    return all_ohlcv


def write_csv(filename, data):
    with open(filename, 'w+') as f:
        writer = csv.writer(f, delimiter=',', quotechar='"',
                            quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['timestamp', 'o', 'h', 'l', 'c', 'v'])
        writer.writerows(data)


def scrape_candles_to_csv(filename, max_retries, exchange, symbol, timeframe, since, limit):
    # Convert start time from string to milliseconds integer if needed.
    if isinstance(since, str):
        since = exchange.parse8601(since)
    try:
        ohlcv = scrape_ohlcv(max_retries, exchange, symbol,
                             timeframe, since, limit)
        write_csv(filename, ohlcv)
        print('Scraping for {} succeeded.'.format(filename))
    except RetryError:
        print('Scraping for {} failed.'.format(filename))


def get_data_filename(pair, tick_size, start, num_ticks):
    return '{}-{}-{}-{}'.format(pair.replace('/', '-'),
                                tick_size, start, str(num_ticks))


def get_data_directory(data_dir, exchange):
    return '{}/{}'.format(data_dir, exchange)


def get_data_path(data_dir, exchange, pair, tick_size, start, num_ticks):
    return '{}/{}.csv'.format(
        get_data_directory(data_dir, exchange),
        get_data_filename(pair, tick_size, start, num_ticks)
    )


# TODO: Eventually create a server and a database for backtest data (instead of CSVs).
def populate(data_dir, exchanges, pairs, tick_size, start, num_ticks):
    for exchange_id in exchanges:
        exchange = getattr(ccxt, exchange_id)({
            'enableRateLimit': True
        })
        exchange.load_markets()
        if not exchange.has['fetchOHLCV']:
            print('{} does not expose OHLCV data.'.format(exchange.id))
            continue
        os.makedirs(get_data_directory(data_dir, exchange_id), exist_ok=True)
        for pair in pairs:
            if not pair in exchange.symbols:
                print('Exchange {} does not trade {}.'.format(exchange_id, pair))
                continue
            print('Downloading price history for {} on exchange {}.'.format(
                pair, exchange_id))
            path = get_data_path(data_dir, exchange_id, pair,
                                 tick_size, start, num_ticks)
            scrape_candles_to_csv(path, MAX_ATTEMPTS, exchange,
                                  pair, tick_size, start, num_ticks)
