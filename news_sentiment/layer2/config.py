# layer2/config.py

from datetime import datetime 
import os

SOURCE_WEIGHTS = {
    "BSE Announcement":  1.00,
    "Economic Times":    0.85,
    "Mint":              0.85,
    "Business Standard": 0.80,
    "Financial Express": 0.75,
    "NDTV Profit":       0.70,
    "Google News":       0.60,
}

FUZZY_THRESHOLD_BSE  = 85
FUZZY_THRESHOLD_NEWS = 88
CONFIDENCE_MIN       = 0.65
BATCH_SIZE           = 16

SCORE_THRESHOLDS = {
    "STRONG_POSITIVE":  0.60,
    "POSITIVE":         0.25,
    "NEGATIVE":        -0.25,
    "STRONG_NEGATIVE": -0.60,
}

# ── ARCHITECTURAL FIX: Dynamic Absolute Pathing ──
# __file__ is at Test/news_sentiment/layer2/config.py
# We traverse up 3 levels to reach the root 'Test' folder, then enter 'data/'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NIFTY500_CSV_PATH = os.path.join(BASE_DIR, "data", "nifty500_constituents.csv")

curr_time = datetime.now().strftime("%Y%m%d_%H%M")
# Do the same for the outputs directory to ensure it saves in the right place
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True) # Ensure the folder exists so it doesn't crash on save
OUTPUT_PATH = os.path.join(OUTPUT_DIR, f'layer_signals_{curr_time}.xlsx')