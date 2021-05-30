# -*- coding: utf-8 -*-
"""
Created on Thu May 27 12:37:56 2021

@author: John Warner

Goals:
Initial version will begin the development of a struct to determine the feasibility 
of 0, 1, 2... DTE SPX or SPY options trades based upon studies of historic data from the 
CBOE or other websites.  

This inital version will select options based upon delta.  This selection method
will sometimes yield multiple options.  When this occurs all selected options will be evaluated.
This will effect any accumulated statistics.

Simulated trades will be executed at specific entry and exit times.  

There will be no "in-trade" management.  

Only days in which the market did not close early will be evaluated.

Only short positions will be evaluated.

Both puts and calls will be evaluated.

Sales will be on the bid and closing trades will be on the ask.

A single contract is traded without consideration of commissions.

Input files are based on the standard CBOE format/column heading .csv files.  
These files are segmented by trading day.

Algorithm:
    1.  Convert all dates to UNIX timestamps
    2.  Convert times to a daily minute count
    3.  Mark selections with the desired DTE AND when trade time (TT) is 
    equal to the desired entry time AND the future trade time is equal
    to the desired exit time.  This is considered a "time alignment"
    4.  Once the time is aligned then I cut the dataframe size down in
    order to improve the processing time.
    5.  For cases where there is a time alignment search for the delta.
    6.  The delta offset will be used in option selection.  The delta
    offset is efined as the range of deltas that will trigger a trade.  
    For example, if a 10 (0.1) delta is desired with the offset at 0.02 
    any delta in the range of 0.08 to 0.12 will be selected.
    7.  When an option is found with the appropriate delta, the bid at
    the entry time and ask at the exit time are used to calcuate a profit.
    8.  Nominally, there should only be one trade per day.  However, because
    of the delta range process there may be multiple options trades in a day.
    This can be seen in the results file.
    9.  for loops are set up to evaluate combinations of calls/puts, deltas,
    and DTE

Date Management:
    Data will be stored in a Windows folder entitled "Options Data".  Within
    this folder each symbol will have a sub-folder.  The name of the sub-folder
    will be the trading symbol.  The raw data will be within the sub_folder.
    Each folder will consist of a single day of quotes.

Future Versions:
    * Settle specific values for delta & delta offset for a more in-depth analysis.
    * Prioritize underlying statistics of interest and additional option
    selection metrics.
    * Add underlying Open, High, & Low.  Any statistics calculated on the underlying
    price will need to be done on a seperate file containing the underlying 
    price data.  In order to reduce run time the options of interest will need
    to be filtered.  Then the filtered options file can be merged with the 
    underlying price data plus any statistics that were generated.
    
"""
import glob, os
import pandas as pd
import numpy as np
    
#
#process_files - gets each file from a directory
#
def process_files():   
        
    os.chdir(feed_dir)
        
    # loop to find and process each file in the directory
    for file in glob.glob("*.csv"): 
        
        optfilename = file.split(".")   #extract filename 
        optfile = optfilename[0]
        
        # Read the file as a dataframe
        df = pd.read_csv(feed_dir + optfile + ".csv", 
                         parse_dates=True, usecols=['root', 'quote_datetime', 'expiration', 'strike', 'option_type', 'delta', 'bid', 'ask'])    
        # Drop nan data
        df = df.dropna() 
        
        # split the quote date and time, further split the hours, min, sec.
        df[['QD','QT']] = df.quote_datetime.str.split(" ",expand=True,)
        df[['Hour','Minute']] = df.QT.str.split(":",expand=True)
        
        # Convert time to "trade times"
        df['TT'] = pd.to_numeric(df['Hour']) * 60 + pd.to_numeric(df['Minute'])
        
        # Convert quote date to unix datetime stamp
        df['QDate'] = (pd.to_datetime(df['QD']).astype(np.int64)//10**9)/86400
        
        # Convert expiration date to unix datetime stamp
        df['EDate'] = (pd.to_datetime(df['expiration']).astype(np.int64)//10**9)/86400
        
        # Save the desired exit bid price
        df['Exit Ask'] = df['ask'].shift(-trade_offset)
        
        # Mark all rows with "x" dte AND trade_entry AND trade_exit times
        df.loc[(df['EDate'] - df['QDate'] == dte) & 
               (df['TT'] == trade_entry) &
               (df['TT'].shift(-trade_offset) == trade_exit), 'Time Align'] = 1
        
        # Now let's cut the dataframe down to size.  
        dfo = df[(df['Time Align'] == 1)]

        # Ensure there is data in the dataframe
        if not(dfo.empty):
            # After this I will only have the following columns to work with but only
            # for the desired expiration date.
            dfo = dfo.filter(['expiration', 'strike', 'option_type', 'delta', 'bid', 'Exit Ask'], axis=1)
            
            # Now search for delta or other signal in the new dataframe - input delta controls the search
            # Bracket the input delta by a delta offset  to find the call & put deltas
            dfo.loc[(round(dfo['delta'],2) <= delta + delta_offset) & 
                   (round(dfo['delta'],2) >= delta - delta_offset), 'Delta Match'] = 1
            
            dfo.loc[(dfo['Delta Match'] == 1), 'Sold Strike'] = dfo['strike']
            dfo.loc[(dfo['Delta Match'] == 1), 'Credit'] = dfo['bid']
            dfo.loc[(dfo['Delta Match'] == 1), 'Debit'] = dfo['Exit Ask']
            dfo['Profit'] = (dfo['Credit'] - dfo['Debit']) * 100
            
            # Summarize
            trades = dfo['Delta Match'].sum()
            net = dfo['Profit'].sum()
            
            print(file, ",", delta, ",", delta_offset, ",", dte, ",", trades, ",", net, file=results_file)
            print(file, ",", delta, ",", delta_offset, ",", dte, ",", trades, ",", net)

        
# get symbol to test
sub_dir = " "
sub_dir = input("Sub Directory to test-->  ")
feed_dir = "C:/Users/WARNE/Desktop/Events v47/Options Data/" + sub_dir + "/"

# record results
results_file = open("C:/Users/WARNE/Desktop/Events v47/Option_Study_Results_" + sub_dir + ".csv", "w")
print("Symbol,Delta,Delta Offset,DTE,Trades,Net", file=results_file)


# Trading variables

# Trade entry & exit times in minutes
# 630 corresponds to 10:30am and 930 corresponds to 3:30pm.  All times are EST.
trade_entry = 630
trade_exit = 930
# number of rows between trade entry & trade exit for 30 min data
trade_offset = 10

# The delta offset is a compromise based on early testing
delta_offset = 0.02

# Vary the DTE
for dte in range(0,4):
    # vary the delta - positive for calls & negative for puts.
    for d_index in range(1,7):
        if d_index == 1:
            delta = 0.1
        if d_index == 2:
            delta = 0.2
        if d_index == 3:
            delta = 0.3
        if d_index == 4:
            delta = -0.1
        if d_index == 5:
            delta = -0.2
        if d_index == 6:
            delta = -0.3

        process_files()

results_file.close()

print("Study done")


