'''
ML-Based Trading Strategy
'''
import cbpro
import zmq
import sys
import json
import time
import os
import pickle
import pandas as pd
import numpy as np
import datetime as dt
# the following libraries are to update the persisted ML model
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
        print("-- Goodbye! --")

def logger_monitor(message, time=True, sep=True):
    # logger and monitor function
    with open(log_file, 'a') as f:
        t = str(dt.datetime.now())
        msg = ''
        if time:
            msg += ',' + t + ','
        if sep:
            msg += 3 * '='
        msg += ',' + message + ','
        # sends the message via the socket
        socket.send_string(msg)
        # writes the message to the log file
        f.write(msg)
        return

def report_positions(pos):
    '''Logs and sends position data'''
    out = ''
    out += ',Going {},'.format(pos) + ','
    time.sleep(0.033) # waits for the order to be executed
    # get orders (will possibly make multiple HTTP requests)
    #get_orders_gen = auth_client.get_orders()
    get_fills = list(fills_gen)
    out += ',' + str(get_fills) + ','
    logger_monitor(out)
    return

# callback function - algo trading minimal working example
# https://en.wikipedia.org/wiki/Minimal_working_example

def trading_mwe(symbol, amount, position, bar, min_bars, twentyfour, df_accounts, df_fills):
    # Welcome message
    print('')
    print('*'*50)
    print('***      Welcome to Tenzin II Crypto Trader   ***')
    print('*'*50)
    print('')
    print('Trading: ', symbol)
    print('Amount per trade: ', amount)
    print('')
    print('Last 24 hrs:')
    print('')
    print('Open: .........', twentyfour['open'])
    print('Last: .........', twentyfour['last'])
    print('High: .........', twentyfour['high'])
    print('Low:    .......', twentyfour['low'])
    print('Volume:  ......', twentyfour['volume'])
    print('30 day Volume: ', twentyfour['volume_30day'])
    print('')
    print('Recent orders: ')
    print(df_fills.loc[-3:,['product_id', 'fee', 'side', 'settled', 'usd_volume']])
    print('')
    print('Account Positions: ')
    print(df_accounts[['currency', 'balance']])
    print('')

    # global variables
    global wsClient, df, dataframe, algorithm, log_file
    # intialize variables
    trading = 'n'   # default == not trading

    # ask to start trading
    trading = input('Start trading? [Y]/[n]:')

    while trading == 'Y':
        while wsClient.data:
            start = time.process_time() # reference for start of trading
            end = start + 10.0             # when to end trading in minutes
            tick = wsClient.data
            dataframe = dataframe.append(tick, ignore_index=True)
            dataframe.index = pd.to_datetime(dataframe['time'], infer_datetime_format=True)
            # resampling of the tick data
            df = dataframe.resample(bar, label='right').last().ffill()

            if len(df) > min_bars:
                min_bars = len(df)
                logger_monitor('NUMBER OF TICKS: {} |'.format(len(dataframe))+\
                'NUMBER OF BARS: {}'.format(min_bars))
                # data processing and feature preparation
                df['Mid'] = df[['price']].mean(axis=1)
                df['Returns'] = np.log(df['Mid']/df['Mid'].shift(1))
                df['Direction'] = np.where(df['Returns'] > 0, 1, -1)
                # picks relevant points
                features = df['Direction'].iloc[-(lags + 1): -1]
                # necessary reshaping
                features = features.values.reshape(1, -1)
                # generates the signal (+1 or -1)
                signal = algorithm.predict(features)[0]

                # logs and sends major financial information
                logger_monitor('MOST RECENT DATA\n'+\
                str(df[['Mid', 'Returns', 'Direction']].tail()),False)
                logger_monitor('\n' + 'features: ' + str(features) + ',' +\
                              'position:  ' + str(position) + ',' +\
                              'signal:    ' + str(signal) + ',', False)

                # trading logic
                if position in [0, -1] and signal == 1:
                    auth_client.place_market_order(product_id = symbol,
                                       side = 'buy', \
                                       funds = amount - position * amount)
                    position = 1
                    report_positions('LONG')

                elif position in [0, 1] and signal == -1:
                    auth_client.place_market_order(product_id = symbol,\
                    side = 'sell', funds = amount + position * amount)
                    position = -1
                    report_positions('SHORT')

                else: # no trade
                    logger_monitor('no trade placed')

                logger_monitor(',****END OF CYCLE****,', False, False)
                #time.sleep(15.0)

            if len(df) > 100:
                # ends the trading session
                # long positions are held, open orders are closed
                logger_monitor(',ending trading session, max # ticks received,',\
                 False, False)
                # cancel orders
                report_positions(',CANCEL ORDERS,')
                auth_client.cancel_all(product_id=symbol)
                logger_monitor(',***CANCELING UNFILLED ORDERS***,')
                # save data
                df.to_csv('tick_history.csv')
                return
            if time.process_time() > end:
                # ends the trading session based on max. time defined by end
                # long positions are held, open orders are closed
                logger_monitor(',ending trading session, time-out end reached,',\
                 False, False)
                # cancel orders
                report_positions(',CANCEL ORDERS,')
                auth_client.cancel_all(product_id=symbol)
                logger_monitor(',***CANCELING UNFILLED ORDERS***,')
                # save data
                df.to_csv('tick_history.csv')
                return

    # Ask to continue trading
    trading = input('Restart trading? [Y]/[n]:')
    if trading == 'n':
        return


if __name__ == '__main__':
    # File path to save data to
    path = os.getcwd()                # for .ipynb implementation
    #path = os.path.dirname(__file__) # for .py implementation

    # log file to record trading
    log_file = 'online_trading.log'

    # loads the persisted trading algorithm object
    algorithm = pickle.load(open('algorithm_dailyBTC.pkl', 'rb'))

    # sets up the socket communication via ZeroMQ (here: "publisher")
    context = zmq.Context()
    socket = context.socket(zmq.PUB)

    # this binds the socket communication to all IP addresses of the machine
    # socket.bind('tcp://0.0.0.0:5555')
    # socket.bind('tcp://*:5555')
    socket.bind('tcp://*:5555')

    # Authentication credentials
    api_key = os.environ.get('CBPRO_SANDBOX_KEY')
    api_secret = os.environ.get('CBPRO_SANDBOX_SECRET')
    passphrase = os.environ.get('CBPRO_SANDBOX_PASSPHRASE')

    # sandbox authenticated client
    auth_client = cbpro.AuthenticatedClient(api_key, api_secret, passphrase, \
                                            api_url='https://api-public.sandbox.pro.coinbase.com')
    # live account authenticated client
    # uses a different set of API access credentials (api_key, api_secret, passphrase)
    # auth_client = cbpro.AuthenticatedCliet(api_key, api_secret, passphrase)

    # parameters for the trading algorithm
    # the trading algorithm runs silently for 500 ticks
    # use stratMonitoring.ipynb to monitor trading activity

    symbol = 'BTC-USD'
    bar = '15s'         # 15s is for testing; reset to trading frequency
    amount = 225        # amount to be traded in $USD
    position = 0        # beginning, neutral, position
    lags = 5            # number of lags for features data

    # minumum number of resampled bars required for the first predicted value (& first trade)
    min_bars = lags + 1

    # orders & fills generators to report positions:
    orders_gen = auth_client.get_orders()
    fills_gen = auth_client.get_fills(product_id=symbol)

    # Get stats for the last 24 hrs
    twentyfour = auth_client.get_product_24hr_stats(symbol)

    # Get filled orders
    all_fills = list(fills_gen)
    df_fills = pd.DataFrame(all_fills)
    #filepath = os.path.join(path, 'fills-{}.csv'.format(now))
    #df_fills.to_csv(filepath)

    # Get account positions
    accounts = auth_client.get_accounts()
    df_accounts = pd.DataFrame(accounts)
    #filepath = os.path.join(path, 'accounts-{}.csv'.format(now))
    #df_accounts.to_csv(filepath)

    # the main asynchronous loop using the callback function
    # Coinbase Pro web socket connection is rate-limited to 4 seconds per request per IP.

    wsClient = MyWebsocketClient()

    dataframe = pd.DataFrame() # dataframe for storing wsClient feed
    df = pd.DataFrame()        # dataframe for resampling wsClient feed

    try:
        while True:
            # start trading
            wsClient.start()
            trading_mwe(symbol, amount, position, bar, min_bars, twentyfour, df_accounts, df_fills)
            # End session?
            tradeMore = input('Continue trading? [Y]/[n]:')
            if tradeMore == 'Y':
                trading_mwe(symbol, amount, position, bar, min_bars, twentyfour, df_accounts, df_fills)
            else:
                print('*** Tenzin trading session ended ***')
                wsClient.close()
                sys.exit(0)
    except KeyboardInterrupt:
        wsClient.close()

    if wsClient.error:
        print('Error - stopping program')
        wsClient.close()
        sys.exit(1)
    else:
        sys.exit(0)
