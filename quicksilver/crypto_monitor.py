import argparse
import csv
import os
import time
from datetime import datetime
import pandas as pd
import cbpro

# Flooid.io
# be curious, think forward, invent the future
# Crypto Trader - Project QuickSilver

def auth_client():
    # Authentication credentials
    key = os.environ.get('CBPRO_SANDBOX_KEY')
    b64secret = os.environ.get('CBPRO_SANDBOX_SECRET')
    passphrase = os.environ.get('CBPRO_SANDBOX_PASSPHRASE')

    #auth_client = cbpro.AuthenticatedClient(key, b64secret, passphrase)
    # Use the sandbox API (requires a different set of API access credentials)
    auth_client = cbpro.AuthenticatedClient(key, b64secret, passphrase,
                                      api_url="https://api-public.sandbox.pro.coinbase.com")
    return auth_client

def get_quote(client, symbol):
    quote = client.get_product_ticker(product_id=symbol)
    print(quote)
    return quote

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose','-v', help='Verbose output', action='store_true')
    parser.add_argument('--symbol','-s', default="BTC-USD", help="What symbol do you want to trade?")
    args = parser.parse_args()
    return args

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    args = get_args()
    print("Starting QuickSilver System")
    print(args)
    # {'trade_id': 157856187,
    # 'price': '56841.91',
    # 'size': '0.00378783',
    # 'time': '2021-04-19T06:45:56.300115Z',
    # 'bid': '56837.35',
    # 'ask': '56837.36',
    # 'volume': '22233.86910903'}

    a_client = auth_client()
    p_client = cbpro.PublicClient()

    if (args.verbose):
        print(a_client.get_accounts())
    today = datetime.now()
    output_file = f"{args.symbol}-{today.strftime('%m%d%y-%H%M')}.csv"

    bitcoin_quotes = pd.DataFrame(columns=['trade_id', 'price', 'size', 'time','bid', 'ask', 'volume'])
    start_time = time.time()
    seconds = 30
    velocity = 0
    rolling_period = 5

    with open(f"data/{output_file}", 'a+', newline='', encoding='utf-8') as csvfile:
        while True:
            current_time = time.time()
            elapsed_time = current_time - start_time

            if elapsed_time > seconds:
                quote = get_quote(p_client,args.symbol)
                bitcoin_quotes = bitcoin_quotes.append(pd.Series(quote), ignore_index=True)
                if (args.verbose): print(quote)
                bitcoin_quotes['std_dev'] = bitcoin_quotes['price'].rolling(rolling_period).std(ddof=0)
                row = bitcoin_quotes.iloc[-1:].to_numpy()[0]
                print(row)
                start_time = time.time()
                current_time = time.time()
                elapsed_time = current_time - start_time

                #write quotes
                writer = csv.writer(csvfile)
                writer.writerow(row)

# TODO
# Build a simple client to ping every X mins and get a quote. Build a Moving average model and volatility.
# Only trade when volatility is < Y
# Calculate volatility for each hour of the day.
# Study volatility vs slope as a risk indicator to stop trading

# System Tenets
# We want a balance between successful trades and max loss/drawdown pct.
# We don't want 90% losers and 10% winners if (classical trend trading)
# We don't want 90% winners and 10% loser if our ROC is too low.
# We will keep the system and models simple.
