'''
# Tenzin Trader - Trading Algorithm
'''
import cbpro
import sys
import json
import time
import os
import pickle
import pandas as pd
import numpy as np
import datetime as dt
# to do: the following libraries are to update the persisted ML model
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score

# overload the on_message behavior of cbpro.WebsocketClient
class MyWebsocketClient(cbpro.WebsocketClient):
    def on_open(self):
        self.url = "wss://ws-feed.pro.coinbase.com/"
        self.products = symbol
        self.channels = ['ticker']
        self.should_print = False

    def on_message(self, msg):
        self.data = msg

    def on_close(self):
        # global variables
        global wsClient, algorithm
        print("WS datafeed closed, attempting restart")
        wsClient.start()
        time.sleep(60)      # give time for wsClient to start datafeed
        trading_mwe(symbol, amount, position, bar, min_bars)
        return

# callback function - algo trading minimal working example
# https://en.wikipedia.org/wiki/Minimal_working_example

def trading_mwe(symbol, amount, position, bar, min_bars):
    # global variables
    global wsClient, algorithm
    df_temp = pd.DataFrame() # dataframe for price series from websocket
    df = pd.DataFrame()      # dataframe for resampling to bars
    # default == trading
    trading = 'Y'
    print('Saving {0} datafeed. Trading starts after {1} bars are saved.'.format(symbol, min_bars))
    
    if trading == 'Y':
        df_temp = pd.read_csv('btc_price_series.csv', index_col=0)
        while wsClient.data:
            tick = wsClient.data
            # resampling of the tick data
            try:
                new_entry = [tick['time'],tick['price']]
                new_entry_series = pd.Series(new_entry, index=df_temp.columns)
                df_temp = df_temp.append(new_entry_series, ignore_index=True)
                df_temp.index = pd.to_datetime(df_temp['time'], infer_datetime_format=True)
                df = df_temp.resample(bar, label='right').last().ffill()
            except (TypeError, ValueError, KeyError, IOError, AttributeError):
                new_entry = [tick['time'],tick['price']]
                new_entry_series = pd.Series(new_entry, index=df_temp.columns)
                df_temp = df_temp.append(new_entry_series, ignore_index=True)
                df_temp.index = pd.to_datetime(df_temp['time'], infer_datetime_format=True)
                df = df_temp.resample(bar, label='right').last().ffill()
            except RuntimeError:
                return
            
            if len(df) > min_bars:
                min_bars = len(df)
                # output to screen
                print('trading in progress...')
                #output to remote monitoring program
                print('NUMBER OF TICKS: {} |'.format(len(df_temp))+\
                'NUMBER OF BARS: {}'.format(min_bars))
                # data processing and feature preparation
                df['price'] = df['price'].astype('float64')
                df['Returns'] = np.log(df['price']/df['price'].shift(1))
                df['Direction'] = np.where(df['Returns'] > 0, 1, -1)
                # picks relevant points
                features = df['Direction'].iloc[-(lags + 1): -1]
                # necessary reshaping
                features = features.values.reshape(1, -1)
                # generates the signal (+1 or -1)
                signal = algorithm.predict(features)[0]
                # stores trade signal
                df['Position'] = position
                df['Signal'] = signal

                # trading logic
                if position in [0, -1] and signal == 1:
                    auth_client.place_market_order(product_id = symbol,
                                       side = 'buy', \
                                       funds = amount - position * amount)
                    position = 1
                    print('LONG')

                elif position in [0, 1] and signal == -1:
                    auth_client.place_market_order(product_id = symbol,\
                    side = 'sell', funds = amount + position * amount)
                    position = -1
                    print('SHORT')

                else: # no trade
                    auth_client.place_market_order(product_id = symbol,\
                    side = 'sell', funds = 0 + position * 0)
                    position = 0
                    print('no trade placed')

                df_temp.reset_index(drop=True, inplace=True)
                df_temp.to_csv('btc_price_series.csv')
                print('****END OF CYCLE****')

            if len(df) > 432:
                # ends the trading session
                # long positions are held, open orders are closed
                print('ending trading session, max # ticks received')
                # cancel orders
                print('***CANCELING UNFILLED ORDERS***')
                auth_client.cancel_all(product_id=symbol)
                trading = 'n'

        return


if __name__ == '__main__':
    
    # loads the persisted trading algorithm object
    algorithm = pd.read_pickle('algorithmBTC.pkl')

    # Authentication credentials
    api_key = os.environ.get('CBPRO_KEY')
    api_secret = os.environ.get('CBPRO_SECRET')
    passphrase = os.environ.get('CBPRO_PASSPHRASE')

    # sandbox authenticated client
    #auth_client = cbpro.AuthenticatedClient(api_key, api_secret, passphrase, \
                                            #api_url='https://api-public.sandbox.pro.coinbase.com')
    # live account authenticated client
    # uses a different set of API access credentials (api_key, api_secret, passphrase)
    auth_client = cbpro.AuthenticatedClient(api_key, api_secret, passphrase, \
                                          api_url='https://api.pro.coinbase.com')

    # parameters for the trading algorithm
    # the trading algorithm runs silently for 500 ticks
    '''
    5 min: 300s, 10 min: 600s, 15 min: 900s, 30 min: 1800s, 45 min: 2700s
    1 hr: 3600s, 2hr: 7200s, 3hr: 10800s, 6hr: 21600s, 9hr: 32400s, 12hr: 43200s, 24hr: 86400s
    'BTC-USD', 'BTC-EUR', 'BTC-GBP', 'ETH-USD'
    '''

    symbol = 'BTC-USD'
    bar = '21600s'      # 15s is for testing; reset to trading frequency
    amount = 25.17      # amount to be traded in $USD - $50 minimum
    position = 0        # beginning, neutral, position
    lags = 13           # number of lags for features data

    # minumum number of resampled bars required for the first predicted value (& first trade)
    min_bars = lags + 1

    # the main asynchronous loop using the callback function
    # Coinbase Pro web socket connection is rate-limited to 4 seconds per request per IP.

    wsClient = MyWebsocketClient()

    try:
        while True:
            # start trading
            wsClient.start()
            time.sleep(60)      # give time for wsClient to start datafeed
            trading_mwe(symbol, amount, position, bar, min_bars)

    except KeyboardInterrupt:
        wsClient.close()

    if wsClient.error:
        print('Error - restarting program')
        wsClient.start()
        time.sleep(60)      # give time for wsClient to start datafeed
        trading_mwe(symbol, amount, position, bar, min_bars)
    else:
        print('Restarting program')
        wsClient.start()
        time.sleep(60)      # give time for wsClient to start datafeed
        trading_mwe(symbol, amount, position, bar, min_bars)
