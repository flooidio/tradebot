'''
# Denali: TD Ameritrade OAuth2 Requests
'''
import argparse
from datetime import date, timedelta
from datetime import datetime as dt
import os
import json
import csv
import pandas as pd
'''
# Purpose: Denali retrieves data from TD Ameritrade's API.

# Requisites:
#    (1) TDAmeritrade.com account
#    (2) developer.TDAmeritrade.com account
#    (3) an app created on the TD Ameritrade developer account
#    (4) client_id stored as an environment variable
#    (5) a refresh token stored as an environment variable

# TD Ameritrade recommends a manual process for requesting a refresh token.

# Ref: TDAmeritradeOAuth2Notes2021.txt

# TD Ameritrade token server url:
# https://api.tdameritrade.com/v1/oauth2/token

# The TD Ameritrade API is the resource server that provides the protected resources when
# a valid request is received with an access token.

# TD Ameritrade resource server base url:
# https://api.tdameritrade.com/v1
'''
from sanction import Client
import time
import toml
import time
import datetime
# Background info for Sanction and its functions:
# https://sanction.readthedocs.io/en/latest/
# https://docs.python.org/2.6/library/urllib2.html

def api_pricehistory(symbol):
    # Price History API
    url = '/{0}/pricehistory'.format(symbol)

    querystring = '?apikey={0}&period=6&frequencyType=daily&frequency=1'.format(client_id)

    # url = url+querystring # querystring not used- throwing errors
    # print statements are used for verbose output:
    # print('constructed url with query string:')
    # print(url)

    headers = {'Authorization': 'Bearer {0}'.format(c.access_token)}
    # print('client app constructed header:')
    # print(headers)

    # API requests are throttled to 120 requests / minute or 1 request every 0.5 sec
    data = c.request(url=url, headers=headers)
    time.sleep(60)  # 60 sec delay per required API request rate >= 0.5 sec

    return data


def api_chains(symbol, strikeCount, includeQuotes, strategy, interval, options_range, fromDate, toDate, expMonth):
    # Option Chains API
    url ='/chains'
    querystring= '?apikey={0}&symbol={1}&strikeCount={2}&includeQuotes={3}&strategy={4}&interval={5}&range={6}\
    &fromDate={7}&toDate={8}&expMonth={9}'.format(client_id, symbol, strikeCount, includeQuotes, strategy, interval,\
                                 options_range, fromDate, toDate, expMonth)

    url = url+querystring
    headers = {'Authorization': 'Bearer {0}'.format(c.access_token)}

    # API requests are throttled to 120 requests / minute or 1 request every 0.5 sec
    data = c.request(url=url, headers=headers)

    return data

def dict2json(data:dict, filename:str):
    with open(filename, "a") as f:
        json.dump(data, f)
    f.close()
    return

#returns a list from a dictionary only containing the specified keys
def filter_fields(dict, keys):
    result = [value for key,value in dict.items() if key in keys]
    return result

#check if directory exists, otherwise create it
def ensure_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"created dir {directory}")

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose','-v', help='Verbose output', action='store_true')
    parser.add_argument('--symbol','-s', default="$SPX.X", help="What symbol do you want to trade? default: SPX")
    parser.add_argument('--interval','-i', type=int, default=30, help="Interval to scan in secs (default: 30 secs)")
    parser.add_argument('--days', '-d', type=int, default=7, help="Number of days to expiration. Default: 7")
    parser.add_argument('--strikes', '-n', default="50", help="Number of strikes above and below. Default: 50")
    parser.add_argument('--auto', '-a', action="store_true", help="Should scanner only capture quotes during US markwt trading hours? (6:30AM PST to 1PM PST)  Default: true")

    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = get_args()
    print("Starting TDAmeritrade Scanner")
    print(args)

    # override existing variable in the environment
    # Define credentials
    client_id =  os.environ.get('TRADEBOT_KEY')                            # api key
    client_secret = os.environ.get('TRADEBOT_TOKEN')
    redirect_uri = 'https://api.tdameritrade.com/v1/oauth2/token' # refresh token

    # However, if there is a .config file, use this instead of os.environ
    if os.path.exists('.config'):
        config = toml.load(".config")
        client_id = config['TDA']['client_id']
        client_secret = config['TDA']['refresh_token']
        redirect_uri = config['TDA']['redirect_uri']

    token_url = 'https://api.tdameritrade.com/v1/oauth2/token'       # token url - issues access tokens

    base_url = 'https://api.tdameritrade.com/v1/marketdata'

    # Instantiate a client to request an access token

    # this requires a previously issued refresh token
    # stored as an environment variable, e.g. client_secret = os.environ.get('autoTraderToken')
    c = Client(token_endpoint=token_url, resource_endpoint=base_url, client_id=client_id, \
               client_secret=client_secret)
    # Request an access token
    # Requests are throttled to 120 requests / minute or 1 request every 0.5 sec
    # Excessive token requests will be discouraged by TD Ameritrade - i.e. rate limiting by IP address, etc.
    c.request_token(grant_type='refresh_token', refresh_token=client_secret, redirect_uri=redirect_uri)

    # Price History API Request
    # ref for stocks: https://www.barchart.com/stocks/most-active/price-volume-leaders
    symbol = args.symbol

    #data1 = api_pricehistory(symbol)

    today = dt.now()
    marketStart = dt.combine(date.today(), datetime.time(0, 2))
    marketEnd =  dt.combine(date.today(), datetime.time(0, 3))
    if today > marketStart and today < marketEnd:
        print("Market open! :)")
        market_open = True
    else:
        print("Market closed :(")
        market_open = False

    #API variables
    symbol = args.symbol
    strikeCount = args.strikes
    includeQuotes = True
    strategy = 'SINGLE'
    interval = 0
    options_range = 'ALL'
    fromDate = date.today()
    toDate = date.today() + timedelta(days=args.days)
    expMonth = 'ALL'
    data2 = {}

    #dict2json(data1, f"{symbol}-{today.strftime('%m%d%y-%H%M')}-price-hist.json")

    # Options Chain API Request
    # ref for options symbols: https://www.barchart.com/options/most-active/stocks
    # ref for API https://developer.tdameritrade.com/option-chains/apis/get/marketdata/chains
    data2 = {} # empty dictionary to update from api_chains()

    # == Full line ==
    #{'putCall': 'PUT', 'symbol': 'SPXW_060721P4105', 'description': 'SPXW Jun 7 2021 4105 Put (PM) (Weekly)',
    # 'exchangeName': 'OPR', 'bid': 0.3, 'ask': 0.4, 'last': 0.3, 'mark': 0.35, 'bidSize': 0, 'askSize': 0,
    # 'bidAskSize': '0X0', 'lastSize': 0, 'highPrice': 0.9, 'lowPrice': 0.3, 'openPrice': 0.0, 'closePrice': 0.35,
    # 'totalVolume': 281, 'tradeDate': None, 'tradeTimeInLong': 1622835684265, 'quoteTimeInLong': 1622838126178,
    # 'netChange': -0.05, 'volatility': 13.992, 'delta': -0.016, 'gamma': 0.001, 'theta': -0.327, 'vega': 0.172,
    # 'rho': -0.007, 'openInterest': 0, 'timeValue': 0.3, 'theoreticalOptionValue': 0.345, 'theoreticalVolatility': 29.0,
    # 'optionDeliverablesList': None, 'strikePrice': 4105.0, 'expirationDate': 1623096000000, 'daysToExpiration': 1,
    # 'expirationType': 'S', 'lastTradingDay': 1623110400000, 'multiplier': 100.0, 'settlementType': 'P',
    # 'deliverableNote': '', 'isIndexOption': None, 'percentChange': -13.14, 'markChange': 0.0,
    # 'markPercentChange': 1.33, 'mini': False, 'inTheMoney': False, 'nonStandard': False}

    filter_keys = ['putCall','symbol', 'bid', 'ask', 'last', 'mark','totalVolume', 'quoteTimeInLong',
                   'volatility', 'delta', 'gamma', 'theta', 'vega', 'openInterest', 'theoreticalOptionValue',
                   'theoreticalVolatility','strikePrice']
    # 'optionDeliverablesList': None, 'strikePrice': 4105.0, 'expirationDate': 1623096000000]
    col = 1
    while True:
        # if Auto is on, only write during US market hours
        today = dt.now()
        marketStart = dt.combine(date.today(), datetime.time(6, 30))
        marketEnd = dt.combine(date.today(), datetime.time(13, 1))
        if args.verbose: print(f"now {today} start {marketStart} end {marketEnd}")
        if today > marketStart and today < marketEnd:
            if market_open == False:
                print("Market open! :)")
            market_open = True
        else:
            if market_open == True:
                print("Market closed :(")
            market_open = False

        if market_open:
            try:
                data2 = api_chains(symbol, strikeCount, includeQuotes, strategy, interval, options_range, fromDate,
                                   toDate, expMonth)
            except:
                print("T", end='')
                c.request_token(grant_type='refresh_token', refresh_token=client_secret, redirect_uri=redirect_uri)
                # time.sleep(60)
                continue

            try:
                # get underlying's price data
                u_last = data2['underlying']['last']
                u_volume = data2['underlying']['totalVolume']
            except Exception as ex:
                print("E", end='')
                print (ex.__class__.__name__)
                u_last = 0
                u_volume = 0
                time.sleep(30)
                continue

            put_options = [[u_last, u_volume, *filter_fields(fields,filter_keys)] for k1, exp in data2['putExpDateMap'].items() for k2, strike in
                           exp.items() for fields in strike]
            call_options = [[u_last, u_volume, *filter_fields(fields,filter_keys)] for k1, exp in data2['callExpDateMap'].items() for k2, strike in
                            exp.items() for fields in strike]
            options = put_options + call_options

            # using csv.writer method from CSV package
            ensure_dir(f"data/{symbol}/{today.strftime('%y%m')}/")
            try:
                with open(f"data/{symbol}/{today.strftime('%y%m')}/{symbol}-{today.strftime('%y%m%d')}-opt-chain.csv", 'a+', newline='',
                          encoding='utf-8') as outfile:
                    write = csv.writer(outfile)
                    write.writerows(options)

            except:
                print("x", end='', flush=True)
                continue
            if col >= 100:
                col = 0
                print("")
            col += 1
            print(".", end='', flush=True)

        time.sleep(args.interval)  # 120 sec delay per required API request rate >= 0.5 sec

        #dict2json(data2, f"{symbol}-{today.strftime('%m%d%y-%H%M')}-opt-chain.json")
