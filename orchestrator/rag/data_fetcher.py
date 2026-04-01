# =============================================================================
# orchestrator/rag/data_fetcher.py
#
# Fetches real market data to build the RAG knowledge base.
# Called once daily by main.py via the smart refresh logic.
#
# Fetches per stock:
#   • Price history + momentum metrics   (yfinance 6mo / 1yr)
#   • Fundamental metrics                (yfinance info)
#   • Technical indicators computed here (RSI, MACD, EMA, BB, OBV)
#   • News headlines                     (4 Indian financial RSS feeds)
#   • Sector index performance           (NSE sector indices)
#
# Returns a flat list of text chunks which embedder.py then vectorises.
# =============================================================================

import yfinance as yf
import feedparser
import numpy as np
from datetime import datetime

NIFTY_UNIVERSE = [
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "HINDUNILVR.NS","SBIN.NS","BHARTIARTL.NS","ITC.NS","KOTAKBANK.NS",
    "LT.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS",
    "TITAN.NS","ULTRACEMCO.NS","BAJFINANCE.NS","WIPRO.NS","NESTLEIND.NS",
    "TECHM.NS","POWERGRID.NS","NTPC.NS","ONGC.NS","COALINDIA.NS",
    "TATAMOTORS.NS","TATASTEEL.NS","JSWSTEEL.NS","HINDALCO.NS","ADANIENT.NS",
    "GRASIM.NS","DRREDDY.NS","CIPLA.NS","DIVISLAB.NS","APOLLOHOSP.NS",
    "BAJAJFINSV.NS","HCLTECH.NS","INDUSINDBK.NS","EICHERMOT.NS","HEROMOTOCO.NS",
    "BRITANNIA.NS","DABUR.NS","GODREJCP.NS","PIDILITIND.NS","BERGEPAINT.NS",
    "SRF.NS","MUTHOOTFIN.NS","CHOLAFIN.NS","PERSISTENT.NS","COFORGE.NS",
    "BANKBARODA.NS","PNB.NS","CANBK.NS","UNIONBANK.NS","FEDERALBNK.NS",
    "IDFCFIRSTB.NS","RBLBANK.NS","BANDHANBNK.NS","AUBANK.NS","YESBANK.NS",
    "VOLTAS.NS","HAVELLS.NS","CROMPTON.NS","POLYCAB.NS","KEI.NS",
    "TATAPOWER.NS","ADANIGREEN.NS","ADANIPORTS.NS","TORNTPOWER.NS","GAIL.NS",
    "IOC.NS","BPCL.NS","HINDPETRO.NS","ZOMATO.NS","PAYTM.NS",
    "TRENT.NS","PAGEIND.NS","VEDL.NS","NMDC.NS","SAIL.NS",
    "BAJAJ-AUTO.NS","BOSCHLTD.NS","MOTHERSON.NS","EXIDEIND.NS","LUPIN.NS",
    "AUROPHARMA.NS","ALKEM.NS","TORNTPHARM.NS","IPCALAB.NS","JUBLFOOD.NS",
    "ASTRAL.NS","SUPREMEIND.NS","LTIM.NS","MPHASIS.NS","KPITTECH.NS",
    "TATAELXSI.NS","ICICIPRULI.NS","HDFCLIFE.NS","SBILIFE.NS","STARHEALTH.NS",
]

NEWS_FEEDS = [
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://feeds.feedburner.com/ndtvprofit-latest",
]

SECTOR_INDICES = {
    "IT":      "^CNX IT",
    "Banking": "^NSEBANK",
    "FMCG":    "^CNXFMCG",
    "Pharma":  "^CNXPHARMA",
    "Auto":    "^CNXAUTO",
    "Metal":   "^CNXMETAL",
    "Nifty500":"^CRSLDX",
}


# ── Technical indicator helpers ───────────────────────────────────────────────

def _rsi(s, period=14):
    delta = s.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    return round((100 - 100 / (1 + gain / loss)).iloc[-1], 2)

def _macd(s):
    macd   = s.ewm(span=12).mean() - s.ewm(span=26).mean()
    signal = macd.ewm(span=9).mean()
    return round(macd.iloc[-1], 4), round(signal.iloc[-1], 4)

def _ema(s):
    e20    = s.ewm(span=20).mean().iloc[-1]
    e50    = s.ewm(span=50).mean().iloc[-1]
    e200   = s.ewm(span=200).mean().iloc[-1]
    price  = s.iloc[-1]
    return round(e20,2), round(e50,2), round(e200,2), e20>e50, price>e200

def _bb(s, period=20):
    sma = s.rolling(period).mean()
    std = s.rolling(period).std()
    pos = (s.iloc[-1] - (sma - 2*std).iloc[-1]) / ((sma + 2*std).iloc[-1] - (sma - 2*std).iloc[-1] + 1e-9)
    return round(pos, 4)

def _obv(close, volume):
    obv = (np.sign(close.diff()) * volume).cumsum()
    return "Rising" if obv.iloc[-1] > obv.iloc[-6] else "Falling"


# ── DataFetcher ───────────────────────────────────────────────────────────────

class DataFetcher:

    def fetch_price_and_technical(self) -> list:
        chunks = []
        print(f"  Fetching price + technical for {len(NIFTY_UNIVERSE)} stocks...")
        for i, sym in enumerate(NIFTY_UNIVERSE):
            try:
                hist  = yf.Ticker(sym).history(period="1y")
                clean = sym.replace(".NS", "")
                if len(hist) < 50:
                    continue
                c, v  = hist["Close"], hist["Volume"]
                price = round(c.iloc[-1], 2)
                r6m   = round(((price - c.iloc[-126]) / c.iloc[-126]) * 100, 2) if len(hist) >= 126 else 0
                r20d  = round(((price - c.iloc[-20])  / c.iloc[-20])  * 100, 2) if len(hist) >= 20  else 0
                rsi                     = _rsi(c)
                macd_l, sig_l           = _macd(c)
                e20, e50, e200, gc, a200 = _ema(c)
                bb_pos                  = _bb(c)
                obv                     = _obv(c, v)
                bulls = sum([rsi>=55, macd_l>sig_l, gc, a200, obv=="Rising", bb_pos>0.5])
                bias  = {6:"Strong Bullish",5:"Strong Bullish",4:"Bullish",
                         3:"Neutral",2:"Bearish",1:"Strong Bearish",0:"Strong Bearish"}[bulls]
                chunks.append({"text": (
                    f"Stock: {clean}\n"
                    f"Price: {price}  6M Return: {r6m}%  20D Momentum: {r20d}%\n"
                    f"52W High: {round(c.max(),2)}  Low: {round(c.min(),2)}\n"
                    f"Technical bias: {bias} ({bulls}/6 bullish)\n"
                    f"RSI: {rsi}  MACD: {macd_l} / {sig_l} ({'Bull' if macd_l>sig_l else 'Bear'})\n"
                    f"EMA 20/50/200: {e20}/{e50}/{e200}  "
                    f"Golden cross: {gc}  Above 200: {a200}\n"
                    f"BB position: {bb_pos}  OBV: {obv}"
                ), "type": "price_technical", "symbol": clean})
                if (i+1) % 20 == 0:
                    print(f"    {i+1}/{len(NIFTY_UNIVERSE)}")
            except Exception:
                continue
        print(f"  → {len(chunks)} price+technical chunks")
        return chunks

    def fetch_fundamentals(self) -> list:
        chunks = []
        print(f"  Fetching fundamentals...")
        for sym in NIFTY_UNIVERSE:
            try:
                info  = yf.Ticker(sym).info
                clean = sym.replace(".NS", "")
                if not info:
                    continue
                chunks.append({"text": (
                    f"Stock: {clean}\n"
                    f"Company: {info.get('longName', clean)}\n"
                    f"Sector: {info.get('sector','N/A')}  Industry: {info.get('industry','N/A')}\n"
                    f"Market cap Cr: {round(info.get('marketCap',0)/1e7,2)}\n"
                    f"PE: {info.get('trailingPE','N/A')}  PB: {info.get('priceToBook','N/A')}\n"
                    f"Debt/Equity: {info.get('debtToEquity','N/A')}  ROE: {info.get('returnOnEquity','N/A')}\n"
                    f"Revenue growth: {info.get('revenueGrowth','N/A')}  "
                    f"Earnings growth: {info.get('earningsGrowth','N/A')}\n"
                    f"Profit margins: {info.get('profitMargins','N/A')}  "
                    f"Operating margins: {info.get('operatingMargins','N/A')}\n"
                    f"Current ratio: {info.get('currentRatio','N/A')}  "
                    f"Dividend yield: {info.get('dividendYield','N/A')}"
                ), "type": "fundamental", "symbol": clean})
            except Exception:
                continue
        print(f"  → {len(chunks)} fundamental chunks")
        return chunks

    def fetch_news(self) -> list:
        chunks = []
        symbols_clean = [s.replace(".NS","") for s in NIFTY_UNIVERSE]
        print(f"  Fetching news from {len(NEWS_FEEDS)} RSS feeds...")
        for url in NEWS_FEEDS:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:60]:
                    title   = entry.get("title", "")
                    summary = entry.get("summary", "")[:400]
                    date    = entry.get("published", str(datetime.now()))
                    related = [s for s in symbols_clean
                               if s.lower() in title.lower() or s.lower() in summary.lower()]
                    chunks.append({"text": (
                        f"News: {title}\n"
                        f"Summary: {summary}\n"
                        f"Date: {date}\n"
                        f"Source: {feed.feed.get('title','Financial News')}\n"
                        f"Related: {', '.join(related) if related else 'General Market'}"
                    ), "type": "news", "symbol": related[0] if related else "MARKET"})
            except Exception:
                continue
        print(f"  → {len(chunks)} news chunks")
        return chunks

    def fetch_sector_performance(self) -> list:
        chunks = []
        print("  Fetching sector performance...")
        for sector, sym in SECTOR_INDICES.items():
            try:
                hist = yf.Ticker(sym).history(period="3mo")
                if hist.empty or len(hist) < 22:
                    continue
                r3m = round(((hist["Close"].iloc[-1]-hist["Close"].iloc[0]) /hist["Close"].iloc[0])*100,2)
                r1m = round(((hist["Close"].iloc[-1]-hist["Close"].iloc[-22])/hist["Close"].iloc[-22])*100,2)
                chunks.append({"text": (
                    f"Sector: {sector}\n"
                    f"3M return: {r3m}%  1M return: {r1m}%\n"
                    f"Trend: {'Outperforming' if r1m>2 else 'Underperforming' if r1m<-2 else 'Neutral'}"
                ), "type": "sector", "symbol": sector})
            except Exception:
                continue
        print(f"  → {len(chunks)} sector chunks")
        return chunks

    def fetch_all(self) -> list:
        print("\n📦  Fetching all RAG data...\n")
        chunks = []
        chunks.extend(self.fetch_price_and_technical())
        chunks.extend(self.fetch_fundamentals())
        chunks.extend(self.fetch_news())
        chunks.extend(self.fetch_sector_performance())
        print(f"\n  Total chunks: {len(chunks)}")
        return chunks