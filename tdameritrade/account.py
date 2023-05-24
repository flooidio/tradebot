import pandas as pd
from datetime import datetime as dt

class Account:
    balance = 0
    options = []
    groups = []
    def __init__(self, balance):
        self.balance = balance
    def __str__(self):
        return str("Account: " + str(self.__dict__))

    def open_trade(self,option):
        self.balance += option.openPrice * 100
        self.options.append(option)
    def open_group_trade(self,group):
        self.balance += group.openPrice * 100
        self.groups.append(group)

    def close_trade(self,option):
        self.balance -= option.closePrice * 100
    def close_group_trade(self,group):
        self.balance -= group.closePrice * 100

    def open(self, qty, price, exit_type, exit_value):
        order = [dt.now(),qty,price,0,price,exit_type,exit_value,True]
        self.pos_df = self.pos_df.append(order)

class Group:
    options = []
    openPrice = 0
    closePrice = 0
    profit = 0
    groupdt = dt.now()
    def __init__(self, group):
        self.openPrice
        self.options = group
    def __str__(self):
        return str("Group: " + str(self.__dict__))

    def open(self, qty, exit_type, exit_value):
        self.opendt = dt.now()
        self.qty = qty
        print([[opt.symbol, opt.openPrice] for opt in self.options])
        self.openPrice = sum([opt.openPrice for opt in self.options])
        self.profit = self.openPrice
        self.exit_type = exit_type  # stop, trailing, limit
        self.exit_value = exit_value * self.openPrice
        self.is_open = True

    def should_exit(self):
        exit = False
        #loop through option quotes to get group price
        group_price = self.get_group_price()

        #print(f"exittype: {self.exit_type} quote:{price} stop:{self.exit_value}")
        if self.exit_type == 'stop':
            #print(f"quote:{group_price} stop:{self.exit_value} diff:{self.exit_value - group_price}")
            if group_price >= self.exit_value: exit= True
        return exit

    def close(self):
        self.closedt = dt.now()
        #self.qty = qty
        self.closePrice = self.get_group_price()
        self.profit = self.openPrice - self.closePrice
        self.is_open = False
        for option in self.options:
            option.close(1)

    def get_group_price(self):
        group_price = 0
        for order in self.options:
            price = (order.quote['mark']).item()
            group_price += price if (order.pos == 'SHORT') else (price * -1)
            #print("quote price: %6.2f  group_price:%6.2f" % (price, group_price))
        return group_price

class Option:
    quote = pd.Series()

    def __init__(self, symbol):
        self.symbol = symbol

    def __str__(self):
        return str("Option: " + str(self.__dict__))

    def open(self, quote, qty, pos, exit_type, exit_value):
        ask = quote['ask'].item()
        bid = quote['bid'].item()
        price = ask if (pos == 'SHORT') else bid * -1
        self.pos = pos
        self.opendt = dt.now()
        self.qty = qty
        self.openPrice = price
        self.profit = self.openPrice
        self.exit_type = exit_type #stop, trailing, limit
        self.exit_value = exit_value * price
        self.exp_date = quote['expDate'].dt.date
        self.expired = False
        self.is_open = True

    def close(self, qty):
        self.closedt = dt.now()
        self.qty = qty
        ask = self.quote['ask'].item()
        bid = self.quote['bid'].item()
        if self.expired:
            #calculate profit/lost based on u_last and option strike
            price = 0.0 if (self.pos == 'LONG') else ask
        else:
            price = ask if (self.pos == 'SHORT') else bid * -1
        self.closePrice = price
        self.profit = self.openPrice - self.closePrice
        self.is_open = False


    def should_exit(self, price):
        exit = False
        #print(f"exittype: {self.exit_type} quote:{price} stop:{self.exit_value}")
        if self.exit_type == 'stop':
            #print(f"quote:{price} stop:{self.exit_value} diff:{self.exit_value - price}")
            if price >= self.exit_value: exit= True
        return exit