"""The `constants` module.

Constants to identify common entities in the code.

"""

# Exchanges.
BITFINEX = "bitfinex"
KRAKEN = "kraken"

# Currencies.
USD = "USD"
USDT = "USDT"
BTC = "BTC"
ETH = "ETH"
XRP = "XRP"

# USD quotes.
BTC_USD = (BTC, USD)
ETH_USD = (ETH, USD)
XRP_USD = (XRP, USD)

# USDT quotes.
BTC_USDT = (BTC, USDT)
ETH_USDT = (ETH, USDT)
XRP_USDT = (XRP, USDT)


def base_currency(pair):
    return pair[0]


def quote_currency(pair):
    return pair[1]
