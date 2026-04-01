import os
import json
from dotenv import load_dotenv
load_dotenv()

from technical_agent.data.data_fetcher import load_nifty500_tickers
from technical_agent.agent import init_fetcher, analyse_stocks

# Init fetcher
init_fetcher(os.getenv("GROWW_API_KEY"), os.getenv("GROWW_SECRET"))

# Test with only 10 stocks
tickers = load_nifty500_tickers()[:150]
print(f"Testing with {len(tickers)} stocks: {tickers}")

import time
start = time.time()

result = analyse_stocks(tickers, "short", 50)

elapsed = round(time.time() - start, 2)
print(f"\nTime taken: {elapsed} seconds")
print(f"Return type: {type(result)}")
print(f"Result: {result}")