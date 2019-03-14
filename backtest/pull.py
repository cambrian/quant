import populator
data_dir = 'data'
# Second item in tuple is max batch size for requests.
exchanges = [('binance', 1000)]
tick_size = '1m'
populator.grab_all_pairs(data_dir, exchanges, tick_size)
