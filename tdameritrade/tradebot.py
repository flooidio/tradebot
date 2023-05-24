'''
# Trade Bot for TDA
# Fredy Villa
# Flooid.io
'''
from account import Account, Group, Option
import argparse
import glob
import os
import json
import traceback

import pandas as pd
import numpy as np
from sanction import Client
import csv
import toml
import time
import datetime
from datetime import datetime as dt
from datetime import date, timedelta
from pytz import timezone

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


def load_dataset(args):
    # loop through days to create dataset
    path = f"{args.dir}/{args.symbol}/2106"  # use your path
    all_files = glob.glob(path + "/*.csv")
    li = []
    cols = ['u_price','u_volume','putCall','symbol', 'bid', 'ask', 'last', 'mark','totalVolume', 'quoteTimeInLong',
                   'volatility', 'delta', 'gamma', 'theta', 'vega', 'openInterest', 'theoreticalOptionValue',
                   'theoreticalVolatility','strikePrice']
    for filename in all_files:
        df = pd.read_csv(filename, header=None, names=cols, na_values={'quoteTimeInLong': 0})
        df.dropna(subset=['quoteTimeInLong'],inplace=True)
        li.append(df)

    option_df = pd.concat(li, axis=0, ignore_index=True)

    #option_df['exp'] = pd.to_datetime(option_df['expirationDate'], unit='ms').apply(lambda x: x.strftime("%Y-%m-%d"))
    option_df.set_index(pd.to_datetime(option_df['quoteTimeInLong'], unit='ms'),inplace=True)
    option_df = option_df.rename_axis('timestamp')
    option_df.index = option_df.index.tz_localize("UTC").tz_convert("US/Pacific")

    #group by 1min buckets since quote timesrtamp is not the same per pull
    quote_list = (option_df.groupby([pd.Grouper(freq='1min'),'symbol','putCall'])).mean()
    quote_list['expDate'] = pd.to_datetime(quote_list.index.get_level_values('symbol').str.extract("(\d+)", expand=False),
                                        format='%m%d%y', errors='ignore')
    # ts_filter = quote_times['timestamp'] > "2021-06-07 13:22:02"

    #print(quote_list.head())
    return quote_list

def calculate_indicators(df):
    return df

def is_eod(row,args):
    #Rule Time Based
    eod = False
    pst = timezone("US/Pacific")
    startTime = datetime.time(12, 59)
    endTime = datetime.time(12, 59)

    trade_datetime = row.index[0][0].to_pydatetime()
    start_time_trigger = pst.localize(dt.combine(trade_datetime.date(), startTime))
    end_time_trigger = pst.localize(dt.combine(trade_datetime.date(), endTime))

    if (trade_datetime >= start_time_trigger) and (trade_datetime <= end_time_trigger):
        print(f"EOD! {trade_datetime}")
        eod = True
    #else:
        #print(f"{type(trade_datetime)} - {type(start_time_trigger)} - {type(end_time_trigger)}")
        #print (f"{trade_datetime} is NOT > {start_time_trigger}. HOLD!") # WHY are dates not working now???
    return eod

def entry_trigger(row,account,args):
    #Rule Time Based
    enter = False
    pst = timezone("US/Pacific")
    startTime = datetime.time(6, 45)
    endTime = datetime.time(6, 45)
    if args.entryh and args.entrym:
        startTime = datetime.time(args.entryh, args.entrym)
        endTime = datetime.time(args.entryh, args.entrym)
    maxSpreads = 1

    #print(row.index[0][0])

    trade_datetime = row.index[0][0].to_pydatetime()
    start_time_trigger = pst.localize(dt.combine(trade_datetime.date(), startTime))
    end_time_trigger = pst.localize(dt.combine(trade_datetime.date(), endTime))
    #marketStart = dt.combine(date.today(), datetime.time(6, 29))
    #marketEnd = dt.combine(date.today(), datetime.time(13, 1))
    if (trade_datetime >= start_time_trigger) and (trade_datetime <= end_time_trigger):
        print(f"{trade_datetime} is > {start_time_trigger}. trade!")
        enter = True
    #else:
        #print(f"{type(trade_datetime)} - {type(start_time_trigger)} - {type(end_time_trigger)}")
        #print (f"{trade_datetime} is NOT > {start_time_trigger}. HOLD!") # WHY are dates not working now???
    return enter

def exit_positions(chain,account,args):
    eod = True if is_eod(chain,args) else False
    # Find out if we should exit and CLOSE trade
    groups = [group for group in account.groups if group.is_open]

    for group in groups:
        quote_list = {}
        #print(order)

        for order in group.options:
            symbol_filter = chain.index.get_level_values('symbol')  == order.symbol
            option_quote = chain.loc[symbol_filter]
            if eod:
                if (option_quote.index.get_level_values('timestamp').date == order.exp_date).bool():
                    print(f"expired! {order.symbol}   underlying: {option_quote['u_price']}  ")
                    order.expired = True
                    order.quote = option_quote
                    order.close(1)
            try:
                if option_quote['bid'].empty | option_quote['ask'].empty:
                    #if args.verbose: print(f"bid empty for {order.symbol} ======================")
                    continue

                else:
                    #add quote to order
                    #quote_list.update({order.symbol: option_quote})
                    order.quote = option_quote

            except:
                traceback.print_exc()
                print(f"ERROR! {type(option_quote['bid'])}  full:{option_quote}")
                exit()

        #calculate group exit:
        #print(f"Quote List: {quote_list}")
        if group.should_exit():
            group.close()
            account.close_group_trade(group)
            if args.verbose:
                print(f"CLOSE group! Bid: {group} ")
            else:
                print(f"CLOSE group! Open: {group.openPrice} Close: {group.closePrice}")

    return account
def select_option(chain, leg, daystoExp):

    #print(chain.index)
    days_filter = ((chain['expDate'].dt.date - chain.index.get_level_values('timestamp').date).dt.days <= daystoExp) & (chain.index.get_level_values('putCall') == leg['type'])
    #putCall_filter = chain[days_filter].index.get_level_values('putCall') == leg['type']

    #print(chain.head())
    list = [ (idx[1], abs( float(leg['delta']) - abs(float(quote['delta'])) ), float(quote['delta'])) for idx,quote in chain.loc[days_filter ].iterrows() ]
    list.sort(key=lambda x: x[1])
    opt_filter = chain.index.get_level_values('symbol') == list[0][0]
    return chain.iloc[opt_filter]

def open_trade(account, row, args):

    strategies = {
        'naked-put-delta-40-200pct': {'daystoExp':1, 'type': 'PUT', 'delta': 0.40, 'exit_type': 'stop', 'exit_value': 3},
        'naked-put-delta-40-150pct': {'daystoExp':1, 'type': 'PUT', 'delta': 0.40, 'exit_type': 'stop', 'exit_value': 2.5},
        'naked-put-delta-40-100pct':  {'daystoExp':7, 'type':'PUT','delta':0.40,'exit_type':'stop','exit_value':2},
        'naked-put-delta-40-80pct': {'daystoExp': 1, 'type': 'PUT', 'delta': 0.40, 'exit_type': 'stop',
                                     'exit_value': 1.8},
        'naked-put-delta-40-50pct': {'daystoExp':1, 'type': 'PUT', 'delta': 0.40, 'exit_type': 'stop', 'exit_value': 1.5},
        'naked-put-delta-40-40pct': {'daystoExp': 1, 'type': 'PUT', 'delta': 0.40, 'exit_type': 'stop',
                                     'exit_value': 1.4},
        'naked-put-delta-40-30pct': {'daystoExp':1, 'type': 'PUT', 'delta': 0.40, 'exit_type': 'stop', 'exit_value': 1.3}
    }
    strategies2 = {
        'dcs-40-20-100pct': { "type": 'debit-credit-spread', 'exit_type': 'stop', 'exit_value': 2, 'daystoExp':1,
                              "legs": [
                                  {'type': 'PUT', 'delta': 0.40, "pos":"SHORT", "qty":1},
                                  {'type': 'PUT', 'delta': 0.20,  "pos":"LONG", "qty":1}
                              ]
                              },
        'dcs-40-20-120pct': {"type": 'debit-credit-spread', 'exit_type': 'stop', 'exit_value': 2.2, 'daystoExp': 1,
                             "legs": [
                                 {'type': 'PUT', 'delta': 0.40, "pos": "SHORT", "qty": 1},
                                 {'type': 'PUT', 'delta': 0.20, "pos": "LONG", "qty": 1}
                             ]
                             },
        'dcs-40-20-150pct': {"type": 'debit-credit-spread', 'exit_type': 'stop', 'exit_value': 2.5, 'daystoExp': 1,
                             "legs": [
                                 {'type': 'PUT', 'delta': 0.40, "pos": "SHORT", "qty": 1},
                                 {'type': 'PUT', 'delta': 0.20, "pos": "LONG", "qty": 1}
                             ]
                             },
        'dcs-40-20-200pct': {"type": 'debit-credit-spread', 'exit_type': 'stop', 'exit_value': 3, 'daystoExp': 1,
                             "legs": [
                                 {'type': 'PUT', 'delta': 0.40, "pos": "SHORT", "qty": 1},
                                 {'type': 'PUT', 'delta': 0.20, "pos": "LONG", "qty": 1}
                             ]
                             },
        'pcs-15-5-100pct': {"type": 'debit-credit-spread', 'exit_type': 'stop', 'exit_value': 2, 'daystoExp': 5,
                             "legs": [
                                 {'type': 'PUT', 'delta': 0.15, "pos": "SHORT", "qty": 1},
                                 {'type': 'PUT', 'delta': 0.05, "pos": "LONG", "qty": 1},

                             ]
                             },
        'ccs-15-5-100pct': {"type": 'debit-credit-spread', 'exit_type': 'stop', 'exit_value': 2, 'daystoExp': 5,
                            "legs": [
                                {'type': 'CALL', 'delta': 0.15, "pos": "SHORT", "qty": 1},
                                {'type': 'CALL', 'delta': 0.05, "pos": "LONG", "qty": 1},

                            ]
                            },
        'ccs-12-5-100pct': {"type": 'debit-credit-spread', 'exit_type': 'stop', 'exit_value': 2, 'daystoExp': 5,
                            "legs": [
                                {'type': 'CALL', 'delta': 0.12, "pos": "SHORT", "qty": 1},
                                {'type': 'CALL', 'delta': 0.05, "pos": "LONG", "qty": 1},

                            ]
                            }
    }

    if args.strategy not in strategies2:
        print(f"Strategy not found {args.strategy}")
        exit()
    filter = strategies2[args.strategy]

    filter.update({'exit_value':args.exitpct})
    opts = []
    for leg in filter['legs']:
        option_quote = select_option(row,leg,filter['daystoExp'])
        #print(option_quote)
        option = Option(option_quote.index[0][1])
        option.open(option_quote,leg['qty'],leg['pos'],filter['exit_type'], filter['exit_value'])
        opts.append((option))

        if args.verbose: print(f"New order: {option}!")
    if len(opts) > 0:
        group = Group(opts)
        group.open(1, filter['exit_type'], filter['exit_value'])
        account.open_group_trade(group)
        if args.verbose: print(f"New Group: {group}!")
    return account

def close_trade(row, args):
    return True

def update_account(account, order):
    return account



def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose','-v', help='Verbose output', action='store_true')
    parser.add_argument('--symbol','-s', default="$SPX.X", help="What symbol do you want to trade? default: SPX")
    parser.add_argument('--startdate','-b', type=str,  help="Start date for backtesting")
    parser.add_argument('--enddate', '-e', type=str, help="End date for backtesting")
    parser.add_argument('--dir', '-d', type=str, default="data", help="Directory for files")
    parser.add_argument('--strategy', '-x', type=str, default="naked-put-delta-40-100pct", help="Strategy to back-test")
    parser.add_argument('--exitpct', '-o', type=float, default=1.0, help="Exit Pct")
    parser.add_argument('--entryh', '-t', type=int, default=6, help="Entry Hour")
    parser.add_argument('--entrym', '-m', type=int, default=45, help="Entry Min")
    parser.add_argument('--file', '-f', type=str, help="CSV output file name")
    args = parser.parse_args()
    return args

def run_backtest(args, bars_df):
    # print(bars_df.describe())
    account = Account(0)

    for key, row in bars_df.groupby(level=0):
        # row = bars_df.loc[key]
        if (entry_trigger(row, account, args)):
            account = open_trade(account, row, args)
            print(account)
        # close positions if exit criteria is hit
        account = exit_positions(row, account, args)
        # account.update_balances()
    return account

def fit_exit_value(args, bars_df):
    #iterate over exit values and calculate max profit
    pct_list = np.arange(1.0, 4.0, 0.1)
    for i in pct_list:
        args.exitpct = i
        account = run_backtest(args, bars_df)
        print(f"Exit pct:{i}  Profit:{account.balance}")

if __name__ == '__main__':
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)

    args = get_args()
    print("Starting Trade Bot Back tester")
    print(args)

    bars_df = load_dataset(args)
    #fit_exit_value(args, bars_df)
    #exit()


    #bars_df = calculate_indicators(bars_df)

    #print(bars_df.describe())
    account = Account(25000.0)
    i = 0


    for key, row in bars_df.groupby(level=0):
        # row = bars_df.loc[key]

        if(entry_trigger(row,account,args)):
            account = open_trade(account,row,args)
            print(account)
        #close positions if exit criteria is hit
        account = exit_positions(row,account,args)
        #account.update_balances()

        #if i > 500000: exit()
        #i += 1

    pd.set_option('display.width', None)
    df  = pd.DataFrame(columns=["groupdt","opendt", "qty", "openPrice", "closePrice", "profit", "exit_type", "exit_value", "is_open"])
    for group in account.groups:
        print("Group: open:%6.2f  close:%6.2f  P/L:%6.2f" % (group.openPrice, group.closePrice, group.profit))
        for order in group.options:
            order.groupdt = group.opendt
            df = df.append(order.__dict__, ignore_index=True)
    print(df.groupby(['groupdt','symbol']).sum())
    print(f"Strategy: {args.strategy}  Profit: {df['profit'].sum() * 100}")

    if (args.file):
        df.to_csv(f"{args.file}.csv")

    exit()

    #TODO
    # 1 - Calculate Expiration
    # 2 - Calculate strikes/capital requirement
    # 3 - Calculate ROC
    # 4 - Add indicators for TSLA maybe SPX
    # 5 - Find Strat mode... try a bunch anbd inf the best strat!




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
    if today >= marketStart and today <= marketEnd:
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
        marketStart = dt.combine(date.today(), datetime.time(6, 29))
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
                print("E", end='')
                c.request_token(grant_type='refresh_token', refresh_token=client_secret, redirect_uri=redirect_uri)
                # time.sleep(60)
                continue

            # get underlying's price data
            u_last = data2['underlying']['last']
            u_volume = data2['underlying']['totalVolume']
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


