import ccxt
import time
import csv
import os
import string

MAX_ATTEMPTS = 5


class RateError(Exception):
    pass


class RetryError(Exception):
    pass


def retry_fetch_ohlcv(max_retries, exchange, symbol, timeframe, since, batch_size):
    for _ in range(max_retries):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, batch_size)
            if ohlcv is not None:
                return ohlcv
        except Exception:
            continue
    raise RetryError('Failed to fetch {} from {} in {} attempts.'
                     .format(symbol, exchange, max_retries))


def scrape_ohlcv(max_retries, exchange, symbol, timeframe, start, limit, batch_size_max):
    timeframe_seconds = exchange.parse_timeframe(timeframe)
    timeframe_ms = timeframe_seconds * 1000
    position = start
    end = start + limit * timeframe_ms
    print('Batch Size: {}'.format(batch_size_max))
    print('Total Entries: {}'.format((end - start) // timeframe_ms))
    while True:
        if position >= end:
            break
        print('Entries Processed: {}'.format(
            (position - start) // timeframe_ms))
        batch_size = max(
            0, min(batch_size_max, (end - position) // timeframe_ms))
        ohlcv = retry_fetch_ohlcv(
            max_retries, exchange, symbol, timeframe, position, batch_size)
        position += batch_size * timeframe_ms
        if len(ohlcv) < batch_size and position < end:
            raise RateError(
                'Exchange returned fewer rows than expected. Try a smaller batch size.')
        yield ohlcv


def write_csv(filename, generator):
    with open(filename, 'w+') as f:
        writer = csv.writer(f, delimiter=',', quotechar='"',
                            quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['timestamp', 'open', 'high',
                         'low', 'close', 'volume'])
        for data in generator:
            writer.writerows(data)


def scrape_ohlcv_to_csv(filename, max_retries, exchange, symbol, timeframe, start, limit,
                        batch_size_max):
    # Convert start time from string to milliseconds integer if needed.
    if isinstance(start, str):
        start = exchange.parse8601(start)
    try:
        ohlcv_generator = scrape_ohlcv(max_retries, exchange, symbol,
                                       timeframe, start, limit, batch_size_max)
        write_csv(filename, ohlcv_generator)
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
    for (exchange_id, batch_size_max) in exchanges:
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
            scrape_ohlcv_to_csv(path, MAX_ATTEMPTS, exchange,
                                pair, tick_size, start, num_ticks, batch_size_max)
