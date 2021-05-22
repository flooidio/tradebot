'''
# Denali: TD Ameritrade OAuth2 Requests
'''
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
    time.sleep(0.5)  # 0.5 sec delay per required API request rate <= 0.5 sec

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
    time.sleep(0.5)  # 0.5 sec delay per required API request rate <= 0.5 sec

    return data

def dict2json(data:dict, filename:str):
    with open(filename, "w") as f:
        json.dump(data, f)
    f.close()
    return

if __name__ == '__main__':

    # Define credentials
    client_id =  os.environ.get('autoTrader')                            # api key
    client_secret = os.environ.get('autoTraderToken')                    # refresh token
    redirect_uri = 'https://api.tdameritrade.com/v1/oauth2/token'    # redirect uri - required for access token request
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
    symbol = 'SPY'

    data1 = api_pricehistory(symbol)

    dict2json(data1, "price_history.json")

    # Options Chain API Request
    # ref for options symbols: https://www.barchart.com/options/most-active/stocks
    # ref for API https://developer.tdameritrade.com/option-chains/apis/get/marketdata/chains
    symbol = 'SPY'
    strikeCount = 10
    includeQuotes = True
    strategy = 'SINGLE'
    interval = 3
    options_range = 'ALL'
    fromDate = '2021-05-01'
    toDate = '2021-06-05'
    expMonth = 'ALL'

    data2 = api_chains(symbol, strikeCount, includeQuotes, strategy, interval, options_range, fromDate, toDate, expMonth)

    dict2json(data2, "opt_chain.json")
