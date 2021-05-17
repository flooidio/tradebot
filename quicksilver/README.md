# Quick Silver Trading System

This system consists of 3 parts:
1) crypto_monitor.py is a CLI that connects to Coinbase and extracts live quotes for a given symbol.
2) TradingStudyV* notebooks are used to conduct analysis and backtests to determine trading strategies
3) crypto_trade (In progress): Executes trading strategy

## Crypto Monitor
To start run:
```shell
python crypto_monitor.py -v -s BTC-USD
```

The monitor will output quote data to the "data" folder

## Trading Studies
To launch a Trading study notebook:
```shell
python -m jupyterlab
```
The start the study in Jupyter Lab

## TODO
* Build a simple client to ping every X mins and get a quote. Build a Moving average model and volatility.
* Only trade when volatility is < Y
* Calculate volatility for each hour of the day.
* Study volatility vs slope as a risk indicator to stop trading

## System Tenets
* We want a balance between successful trades and max loss/drawdown pct.
* We don't want 90% losers and 10% winners if (classical trend trading)
* We don't want 90% winners and 10% loser if our ROC is too low.
* We will keep the system and models simple.