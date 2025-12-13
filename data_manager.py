import json
import os
import pandas as pd
from config import DATA_FILE, ETF_DETAILS_FILE

def load_etf_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_etf_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_etf_details():
    if os.path.exists(ETF_DETAILS_FILE):
        return pd.read_csv(ETF_DETAILS_FILE)
    return pd.DataFrame()

def save_etf_details(df):
    df.to_csv(ETF_DETAILS_FILE, index=False)