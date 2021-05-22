'''
# Options Analysis
'''
import os
import json
import pandas as pd
import numpy as np
import backtrader

# Load Data
def read_json(filename:str):
    with open(filename, "r") as f:
        data = json.load(f)
        f.close()
    return data

def json_extract(obj, key):
    arr = []

    def extract(obj, arr, key):
        if isinstance(obj, dict):
            for k, v in obj.items():
                

f1 = 'price_history.json'
f2 = 'opt_chain.json'

price = read_json(f1)
opt_chain = read_json(f2)
