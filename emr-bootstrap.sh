#!/bin/bash
# TODO: Remove me.
sudo python3 -m pip install --upgrade pip
sudo yum -y install gcc postgresql-devel
sudo python3 -m pip install bitfinex-v2 ccxt hyperopt krakenex matplotlib \
	numpy numpy-ringbuffer pandas psycopg2 sklearn statsmodels sqlalchemy tables \
	tqdm websocket-client
git clone https://1dd1ad0722ea041405d443520b319f968181febd@github.com/cambrian/quant.git
