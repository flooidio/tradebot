#
# Python Module with Class
# for Vectorized Backtesting
# of price trend strategies
#
# Code structure modelled after SMAVectorBacketester.py, 04_pyalgo.ipynb
# Python for Alogrithmic Trading
# (c) Dr. Yves J. Hilpisch
# The Python Quants GmbH
#
# PyAlgo Certificate - Final Project
# Author: Joe Wojniak
# 2021-09-03
#
import numpy as np
import pandas as pd
import os
from datetime import datetime, date, time, timedelta
from scipy.optimize import brute
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor
import pickle
from pylab import plt, mpl
plt.style.use('seaborn')
mpl.rcParams['font.family']='serif'

class TrendVectorBacktester(object):
    ''' Class for vectorized backesting of trend-based option trading strategies.

    Attributes
    ==========
    symbol: str
        underlying equity of the options being traded
    year: str
        year for which data is to be loaded, i.e. ge.stock.20080101.1231.csv
        is the stock data for symbol ge for 2008-01-01 to 2008-12-31, in format
        %Y-%m-%d.
    parameters for calculating order entry signals (a.k.a. buy signals):
    K: int
        time window in days for %K stochastic oscillator
    K_low: int
        value where K is oversold
    K_high: int
        value where K is overbought
    K_pos_change: int
        positive change in K_change, confirms direction of price action
    K_neg_change: int
        negative change in K_change, confirms direction of price action
    K_lag: int
        number of periods to lag K, used to calculate K_change
        K_change = K - K_lag
    SMA: int
        time window in days for SMA
    parameters for selecting which options to buy:
    DTE: timedelta
        days to expiration
    ITM: int
        how far in the money the option is
    OI: int
        open interest, the number of active contracts
    PRICE: float
        the price of the option
    start: str
        start date for row selection
    end: str
        end date for row selection
    parameter to minimize the amount of information displayed:
    print_true: boolean
        print_true is used to minimize displayed output when the
        optimize_parameters method is called
        if print_true == True, display output to screen
        else minimize the output displayed to screen
    Ns: int
        Ns is the number of grid search points used by the SciPy brute algorithm

    Methods
    =======
    get_stock_ data & get_option_data:
        retrieves and prepares the base datasets:
        1. price series data for the underlying
        2. options chain for puts and calls on the underlying
    set_parameters:
        sets new K and SMA set_parameters
    run_strategy():
        runs the backtest for the trend-following strategy
        SVR: boolean - utilizes SVR model to predict underlying's next period returns
    plot_results:
        plots the performance of the strategy compared to the S&P 500 benchmark
    update_and_run:
        updates buy signal parameters (K, K_lag, SMA)
    optimize_parameters:
        optimizes the parameters of the buy signal logic to maximize strategy returns
    '''

    def __init__(self, symbol, year, K, K_low, K_high, K_pos_change, K_neg_change, K_lag, SMA, DTE, ITM, OI, PRICE, start, end,\
    print_true, Ns=20):
        self.symbol = symbol
        self.year = year
        self.K = K
        self.K_low = K_low
        self.K_high = K_high
        self.K_pos_change = K_pos_change
        self.K_neg_change = K_neg_change
        self.K_lag = K_lag
        self.SMA = SMA
        self.DTE = DTE
        self.ITM = ITM
        self.OI = OI
        self.PRICE = PRICE
        self.start = start
        self.end = end
        self.print_true = print_true
        self.Ns = Ns
        self.results = None
        print('Getting stock data')
        self.get_stock_data()
        print('Getting option data')
        self.get_option_data()
        print('Object initialization complete.')

    def get_stock_data(self):
        ''' Retrieves and prepares the underlying's data.
        '''
        raw_stock = pd.read_csv('ge.stock.'+self.year+'0101.1231.csv', index_col=0, \
        parse_dates = True, infer_datetime_format=True)
        raw_stock = raw_stock.loc[self.year+'-'+self.start:self.year+'-'+self.end]
        raw_stock = raw_stock.loc[(raw_stock!=0).all(axis=1)]
        print('Stock data load successful.')
        ''' Calculate %K stochastic oscillator
        '''
        highs = raw_stock.iloc[:,1]
        lows = raw_stock.iloc[:,2]
        max_hi = highs.rolling(self.K).max()
        min_low = lows.rolling(self.K).min()
        '''Shift K & mid-price to avoid foresight bias
        '''
        raw_stock['K'] = (100*(highs-min_low)/(max_hi-min_low)).shift(1)
        raw_stock['K_lag'] = raw_stock['K'].shift(periods=self.K_lag)
        raw_stock['K_change'] = raw_stock['K']-raw_stock['K_lag']
        print('%K stochastic oscillator calculated.')
        ''' Calculate SMA
        '''
        raw_stock['mid'] = ((raw_stock.iloc[:,1]+raw_stock.iloc[:,2])/2).shift(1)
        raw_stock['SMA'] = raw_stock['mid'].rolling(self.SMA).mean()
        raw_stock['mid'] = np.around(raw_stock['mid'])
        print('SMA calculated.')
        self.stock_data = raw_stock

    def get_option_data(self):
        ''' Load prepared data or load & prepare raw data
        '''
        if os.path.exists(self.symbol+'_'+self.year+'_raw_options.csv') & \
        os.path.exists(self.symbol+'_'+self.year+'_options_returns.csv') == True:
            self.option_data = pd.read_csv(self.symbol+'_'+self.year+'_raw_options.csv', index_col=0, \
            parse_dates=True, infer_datetime_format=True)
            self.option_data[' expiration'] = pd.to_datetime(self.option_data[' expiration'])
            print('Loaded datafile: '+self.symbol+'_'+self.year+'_raw_options.csv')
            self.option_rets = pd.read_csv(self.symbol+'_'+self.year+'_options_returns.csv', index_col=0, \
            parse_dates=True, infer_datetime_format=True)
            print('Loaded datafile: '+self.symbol+'_'+self.year+'_options_returns.csv')
        else:
            ''' Retrieves and prepares the option chain data.
            '''
            raw_options = pd.read_csv(self.symbol+'.options.'+self.year+'0101.1231.csv', index_col=0, \
            parse_dates = True, infer_datetime_format=True)
            raw_options = raw_options.loc[self.year+'-'+self.start:self.year+'-'+self.end]
            raw_options.fillna(method='ffill', inplace=True)
            ''' Option trading symbols are reused 6 months after expiration.
                Remove options that expire in the following year (i.e. after Dec-31)
            '''
            expiration_year = str(int(self.year)+1)
            raw_options = raw_options.drop(raw_options[raw_options[' expiration'].str.match('0000-00-00')].index)
            raw_options[' expiration'] = pd.to_datetime(raw_options[' expiration'],\
            infer_datetime_format=True)
            raw_options = raw_options[(raw_options[' expiration']<datetime.strptime\
            (expiration_year+'-01-01', '%Y-%m-%d'))]
            print('Preparing options data. Please be patient.')
            options_prices = pd.DataFrame(index=raw_options.index)
            for symbol in raw_options[' symbol']:
                options_prices[symbol] = raw_options.loc[(raw_options[' symbol']==symbol),\
                 ' price']
            raw_options.drop_duplicates(inplace=True)
            raw_options.to_csv(self.symbol+'_'+self.year+'_raw_options.csv')
            self.option_data = raw_options
            options_returns = np.log(options_prices/options_prices.shift(1))
            options_returns.replace([np.inf, -np.inf], np.nan, inplace=True)
            options_returns.drop_duplicates(inplace=True)
            options_returns.to_csv(self.symbol+'_'+self.year+'_options_returns.csv')
            self.option_rets = options_returns
            print('Options data prepared and returns calculated.')

    def set_parameters(self, year=None, K=None, K_low=None, K_high=None, \
    K_pos_change=None, K_neg_change=None, K_lag=None, SMA=None, DTE=None, \
    ITM=None, OI=None, PRICE=None, print_true=None, Ns=None):
        ''' Updates year, K, K_low, K_high, K_pos_change, K_neg_change, K_lag, SMA, DTE,\
        ITM, OI, and PRICE parameters and resp. time series
        '''
        if year is not None:
            self.year = year
        if K_lag is not None:
            self.K_lag = K_lag
        if K is not None:
            self.K = K
            highs = self.stock_data.iloc[:,1]
            lows = self.stock_data.iloc[:,2]
            max_hi = highs.rolling(self.K).max()
            min_low = lows.rolling(self.K).min()
            self.stock_data['K'] = (100*(highs-min_low)/(max_hi-min_low)).shift(periods=1)
            self.stock_data['K_lag'] = self.stock_data['K'].shift(periods=self.K_lag)
            self.stock_data['K_change'] = self.stock_data['K']-self.stock_data['K_lag']
        if K_low is not None:
            self.K_low = K_low
        if K_high is not None:
            self.K_high = K_high
        if K_pos_change is not None:
            self.K_pos_change = K_pos_change
        if K_neg_change is not None:
            self.K_neg_change = K_neg_change
        if SMA is not None:
            self.SMA = SMA
            self.stock_data['SMA'] = self.stock_data['mid'].rolling(self.SMA).mean()
        if DTE is not None:
            self.DTE = DTE
        if ITM is not None:
            self.ITM = ITM
        if OI is not None:
            self.OI = OI
        if PRICE is not None:
            self.PRICE = PRICE
        if print_true is not None:
            self.print_true = print_true
        if Ns is not None:
            self.Ns = Ns

    def run_strategy(self, SVR=False, RFR=False):
        ''' Backtest the trading strategy.
        '''
        stock_data = self.stock_data.copy()
        if SVR==True:
            long_model = pd.read_pickle('long_model-2021-09-03_1.pkl')
            short_model = pd.read_pickle('short_model-2021-09-03_1.pkl')
            i = 1
            while i < 5:
                stock_data['mid_'+str(i)] = stock_data['mid'].shift(i)
                i = i + 1
            cols = ['mid', 'mid_1', 'mid_2', 'mid_3', 'mid_4']
            stock_data.dropna(inplace=True)
            stock_data['predict_lng'] = long_model.predict(stock_data[cols])
            stock_data['predict_shrt'] = short_model.predict(stock_data[cols])
            stock_data['buy_signal'] = np.where(stock_data['predict_lng']>0.02, 1, 0)
            stock_data['buy_signal'] = np.where(stock_data['predict_shrt']>0.02, 1, 0)
        if RFR==True:
            regr_long_model = pd.read_pickle('regr_long_model-2021-09-03.pkl')
            regr_short_model = pd.read_pickle('regr_short_model-2021-09-03.pkl')
            i = 1
            while i < 5:
                stock_data['mid_'+str(i)] = stock_data['mid'].shift(i)
                i = i + 1
            cols = ['mid', 'mid_1', 'mid_2', 'mid_3', 'mid_4']
            stock_data.dropna(inplace=True)
            stock_data['predict_lng'] = regr_long_model.predict(stock_data[cols])
            stock_data['predict_shrt'] = regr_short_model.predict(stock_data[cols])
            stock_data['buy_signal'] = np.where(stock_data['predict_lng']>0.02, 1, 0)
            stock_data['buy_signal'] = np.where(stock_data['predict_shrt']>0.02, 1, 0)
        else:
            stock_data['trend'] = np.where(stock_data['mid']>stock_data['SMA'], 1, -1)
            stock_data['buy_call'] = np.where((stock_data['trend']==1)&(stock_data['K']<=self.K_low), 1, 0)
            stock_data['buy_put'] = np.where((stock_data['trend']==-1)&(stock_data['K']>=self.K_high), 1, 0)
            stock_data['buy_signal'] = np.where((stock_data['buy_call']==1)&(stock_data['K_change']>=5), 1, 0)
            stock_data['buy_signal'] = np.where((stock_data['buy_put']==1)&(stock_data['K_change']<=-5), 1, 0)
        ''' Select options to buy
        '''
        option_data = self.option_data.copy()
        trades = option_data.merge(stock_data[['mid', 'buy_signal']], how='left',\
        left_index=True, right_index=True)
        puts = trades.loc[(trades[' put/call']=='P')&(trades['buy_signal']==1)&\
        (trades[' strike']==(trades['mid']-self.ITM))&(trades[' expiration']-trades.index>=timedelta(self.DTE))&\
        (trades[' open interest']>self.OI)&(trades[' price']<=(0.5*(trades[' ask']+trades[' bid'])))&\
        (trades[' price']<=self.PRICE)]
        calls = trades.loc[(trades[' put/call']=='C')&(trades['buy_signal']==1)&\
        (trades[' strike']==(trades['mid']+self.ITM))&(trades[' expiration']-trades.index>=timedelta(self.DTE))&\
        (trades[' open interest']>self.OI)&(trades[' price']<=(0.5*(trades[' ask']+trades[' bid'])))&\
        (trades[' price']<=self.PRICE)]
        ''' Evaluate strategy options_returns
        '''
        options_returns = self.option_rets.copy()
        cum_returns = pd.DataFrame(index=options_returns.index)
        columns = list(options_returns.columns)
        for col in columns:
            cum_returns[col] = options_returns[col].cumsum().apply(np.exp)
        trades_array = puts[' symbol'].drop_duplicates().values
        trades_array = np.append(trades_array, calls[' symbol'].drop_duplicates().values)
        strat_crets = pd.DataFrame(index=options_returns.index)
        for trade in trades_array:
            strat_crets[trade] = cum_returns[trade]
        self.results = strat_crets
        # gross performance of the strategy
        aperf = 0
        for trade in trades_array:
            if strat_crets[trade].dropna().empty==True:
                continue
            else:
                aperf = aperf + strat_crets[trade].dropna().iloc[-1]
        # out-/underperformance of strategy
        underlying_short_rets = np.log(stock_data['mid'].shift(1)/stock_data['mid'])
        underlying_short_perf = np.exp(underlying_short_rets.sum())
        underlying_long_rets = np.log(stock_data['mid']/stock_data['mid'].shift(1))
        underlying_long_perf = np.exp(underlying_long_rets.sum())
        operf = aperf - underlying_short_perf - underlying_long_perf
        if self.print_true:
            print('='*35)
            print('Strategy performance: ', round(aperf, 2))
            print('Underlying\'s short performance: ', round(underlying_short_perf,2))
            print('Underlying\'s long performance: ', round(underlying_long_perf,2))
            print('Strategy outperformance: ', round(operf,2))
        ''' Calculate the Kelly criteria f for the strategy
        '''
        wins = 0
        wins_sum = 0.0
        losses = 0
        losses_sum = 0.0
        f = 1.0

        for col in strat_crets.columns:
            if strat_crets[col].dropna().empty==True:
                continue
            elif strat_crets[col].dropna().iloc[-1] > 1.0:
                wins = wins + 1
                wins_sum = wins_sum + strat_crets[col].dropna().iloc[-1]
            else:
                losses = losses + 1
                losses_sum = losses_sum + strat_crets[col].dropna().iloc[-1]
        if losses==0:
            if self.print_true:
                print('Number of trades made: ', str(wins+losses))
                print('Trades won: ', str(wins))
                print('Trades lost: ', str(losses))
                print('Kelly criteria is N/A')
                print('='*35)
        elif wins_sum*losses_sum!=0:
            p = wins/(wins+losses)
            f = p/losses_sum + (1-p)/wins_sum
            if self.print_true:
                print('Strategy Kelly criteria f: ', round(f, 2))
                print('='*35)
        return round(aperf, 2), round(operf, 2), round(f, 2)

    def plot_results(self, legend=True):
        ''' Plots the cumulative performance of the trading strategy
        compared to the symbol.
        '''
        if self.results is None:
            print('No results to plot yet. Run a strategy.')
        title = '%s | Year:%s K_period=%d, K_lag=%d, SMA=%d' % (self.symbol, self.year,\
        self.K, self.K_lag, self.SMA)
        self.results.plot(title=title, legend=legend, figsize=(10,6))

    def update_and_run(self, param_tuple):
        ''' Updates K, K_lag, and SMA parameters and returns the negative \
        absolute underperformance (for minimization algorithm).

        Parameters
        ==========
        K: tuple
            K parameter tuple
        K_lag: tuple
            K_lag period parameter tuple
        SMA: tuple
            SMA parameter tuple
        '''
        self.set_parameters(K=int(param_tuple[0]), K_lag=int(param_tuple[1]), SMA=int(param_tuple[2]))
        return -self.run_strategy()[0]

    def optimize_parameters(self, K_range, K_lag_range, SMA_range):
        ''' Finds global maximum given the K, K_lag, and SMA parameter ranges.

        Parameters
        ==========
        K_range, K_lag_range, SMA_range: tuple
            tuples of the form (start, end, step size)
        '''
        opt = brute(self.update_and_run, (K_range, K_lag_range, SMA_range), Ns=self.Ns, finish=None)
        return opt, -self.update_and_run(opt)


if __name__ == '__main__':
    ''' Backtester object trend_bt parameters:
            symbol, year, K, K_low, K_high, K_pos_change, K_neg_change, K_lag, SMA, DTE, ITM, OI, PRICE, start, end
    '''
    trend_bt = TrendVectorBacktester('ge', '2008', 14, 40, 60, 5, -5, 1, 50, 45, 2, 100, 2.50, '01-01', '12-31', True)
    print(trend_bt.run_strategy())
    trend_bt.set_parameters(K=84, K_low=40, K_high=60, K_pos_change=5, K_neg_change=-5,\
     K_lag=2, SMA=100, DTE=1, ITM=1, OI=100, PRICE=2.50, print_true=False, Ns=10)
    print(trend_bt.run_strategy())
    print(trend_bt.optimize_parameters((10, 90, 10), (1, 7, 2), (2, 112, 22)))
