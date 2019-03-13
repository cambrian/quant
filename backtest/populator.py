import ccxt
import time
import csv
import os
import string

MAX_ATTEMPTS = 5

# subject to debate/change, currently top 20 highest volume coins on CMC
good_coins = ['BTC', 'USD', 'ETH', 'LTC', 'EOS', 'USDT', 'XRP', 'QTUM', 'NEO', 'DASH', 'ZEC', 'BCH', 'ETC', 'BNB', 'XLM', 'TRX', 'ONT', 'AE', 'OMG', 'BSV']

class RetryError(Exception):
    pass


def timeframe_to_ms(exchange, timeframe):
    timeframe_seconds = exchange.parse_timeframe(timeframe)
    return timeframe_seconds * 1000


def retry_fetch_ohlcv(max_retries, exchange, symbol, timeframe, since, batch_size):
    for _ in range(max_retries):
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, batch_size)
            if ohlcv is not None and len(ohlcv) > 0:
                return ohlcv
        except Exception:
            continue
    raise RetryError('Failed to fetch {} from {} in {} attempts.'
                     .format(symbol, exchange, max_retries))


def scrape_ohlcv(max_retries, exchange, symbol, timeframe, start, limit, batch_size_max):
    timeframe_ms = timeframe_to_ms(exchange, timeframe)
    position = start
    end = start + limit * timeframe_ms
    print('Batch Size: {}'.format(batch_size_max))
    print('Total Entries: {}'.format((end - start) // timeframe_ms))
    print('Note that some entries might not exist because they predate exchange history.')
    while True:
        if position >= end:
            break
        print('Entries Processed: {}'.format(
            (position - start) // timeframe_ms))
        batch_size = max(
            0, min(batch_size_max, (end - position) // timeframe_ms))
        ohlcv = retry_fetch_ohlcv(
            max_retries, exchange, symbol, timeframe, position, batch_size)
        position = ohlcv[-1][0] + timeframe_ms
        if len(ohlcv) < batch_size and position < end:
            print('Warning: Exchange returned fewer rows than expected.')
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
def populate(data_dir, exchanges, pairs, tick_size, start, num_ticks=None):
    for (exchange_id, batch_size_max) in exchanges:
        exchange = getattr(ccxt, exchange_id)({
            'enableRateLimit': True
        })
        exchange.load_markets()
        if not exchange.has['fetchOHLCV']:
            print('{} does not expose OHLCV data.'.format(exchange.id))
            continue
        os.makedirs(get_data_directory(data_dir, exchange_id), exist_ok=True)
        # Convert start time from string to milliseconds integer if needed.
        if isinstance(start, str):
            start_ms = exchange.parse8601(start)
        if num_ticks is None:
            num_ticks = (exchange.milliseconds() -
                         start_ms) // timeframe_to_ms(exchange, tick_size)
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

def grab_all_pairs(data_dir, exchanges, tick_size):
    print("Chang")
    for (exchange_id, batch_size_max) in exchanges:
        exchange = getattr(ccxt, exchange_id)({
            'enableRateLimit': True
        })
        exchange.load_markets()
        good_symbols = list(filter(lambda x: x.split('/')[0] in good_coins and x.split('/')[1] in good_coins, exchange.symbols))
        populate(data_dir, [(exchange_id, batch_size_max)], good_symbols, tick_size, '2000-01-01T00:00:00Z')