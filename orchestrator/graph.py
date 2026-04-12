# =============================================================================
# orchestrator/graph.py
#
# LangGraph orchestrator — the single brain of the trading platform.
#
# ARCHITECTURE:
#   All three agents run as FIXED graph nodes — no LLM involvement.
#   LLM is only used to make_final_decision for per-stock reasoning.
#
# FLOW:
#   MEDIUM : collect_input → run_fa (nos vary acc. to threshold ) → run_ta → run_news → decide → report
#   SWING  : collect_input → run_ta (500) → run_news → decide → report
#   SHORT  : collect_input → run_ta (500) → run_news → decide → report
# =============================================================================

import json
import os
import logging
from typing import TypedDict

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from orchestrator.rag.retriever import Retriever
from orchestrator.context_builder import ContextBuilder
from fundamental_agent.agent import run_fundamental_analysis
from technical_agent.agent import run_technical_analysis
from news_sentiment.tool import run_news_sentiment
from utils import load_nifty500_tickers

logger = logging.getLogger(__name__)

# We cap the number of stocks we pass to the LLM for final decision to keep the prompt manageable.
MAX_DECISION_STOCKS = 20

_decision_llm = None

def _get_decision_llm():
    global _decision_llm
    if _decision_llm is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise EnvironmentError("GROQ_API_KEY not set.")
        _decision_llm = ChatGroq(
                            model="llama-3.3-70b-versatile", 
                            temperature=0.1, 
                            api_key=key,
                            model_kwargs={"response_format": {"type": "json_object"}}
                        )
        logger.info("Decision LLM initialised.")
    return _decision_llm


_strategy_rag = None
def _get_strategy_rag():
    global _strategy_rag
    if _strategy_rag is None:
        _strategy_rag = Retriever()
    return _strategy_rag


# ── State ─────────────────────────────────────────────────────────────────────

class TradingState(TypedDict):
    amount:              float
    risk:                str
    trade_type:          str
    fundamental_results: list
    technical_results:   list
    news_results:        list
    market_regime:       str
    candidates:          list
    decisions:           list
    abort_reason:        str


# ── Node 1: collect_user_input ────────────────────────────────────────────────

def collect_user_input(state: TradingState) -> TradingState:
    print("\n" + "=" * 62)
    print("          AUTONOMOUS TRADING PLATFORM")
    print("=" * 62)

    amount = float(input("\n  How much do you want to invest? (₹): "))

    print("\n  Risk Appetite:")
    print("    1. Low    — capital preservation priority")
    print("    2. Medium — balanced risk / reward")
    print("    3. High   — aggressive, momentum driven")
    risk = {"1": "low", "2": "medium", "3": "high"}.get(
        input("\n    Choose (1/2/3): ").strip(), "medium"
    )

    print("\n  Trade Type:")
    print("    1. Medium  (3-6 months)")
    print("    2. Short   (2-8 weeks)")
    print("    3. Swing   (2-10 days)")
    trade_type = {"1": "medium", "2": "short", "3": "swing"}.get(
        input("\n    Choose (1/2/3): ").strip(), "swing"
    )

    print(f"\n  ₹{amount:,.2f}  |  {risk.upper()} risk  |  {trade_type.upper()} trade\n")

    return {
        **state,
        "amount":              amount,
        "risk":                risk,
        "trade_type":          trade_type,
        "fundamental_results": [],
        "technical_results":   [],
        "news_results":        [],
        "market_regime":       "unknown",
        "candidates":          [],
        "decisions":           [],
        "abort_reason":        "",
    }


# ── Node 2: run_fa_node ───────────────────────────────────────────────────────

def run_fa_node(state: TradingState) -> TradingState:
    """
    Runs Fundamental Analysis as a fixed graph node.
    Only runs for MEDIUM trades. Skipped for swing/short.
    Returns threshold-passed candidates for TA to analyse.
    """
    if state["trade_type"] != "medium":
        logger.info("FA skipped — not a medium trade")
        return state

    logger.info("\nRunning Fundamental Analysis on Nifty500 stocks...")

    try:
        tickers = load_nifty500_tickers()
        result = run_fundamental_analysis.invoke({"tickers": tickers, "risk_profile": state["risk"]})

        if isinstance(result, str):
            result = json.loads(result)

        candidates  = result.get("candidates", [])
        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

        # We pass ALL FA candidates to TA (no slicing)
        candidates_list = [c["ticker"] for c in candidates]

        logger.info(f"FA complete: {len(candidates)} candidates selected for TA")

        return {
            **state,
            "fundamental_results": candidates,
            "candidates":          candidates_list,
        }

    except Exception as e:
        logger.error(f"FA node failed: {e}")
        return state


# ── Node 3: run_ta_node ───────────────────────────────────────────────────────

def run_ta_node(state: TradingState) -> TradingState:
    """
    Runs Technical Analysis as a fixed graph node.
    MEDIUM : runs on FA selected symbols
    SWING/SHORT : runs on full Nifty 500
    Always runs — for all trade types.
    """
    trade_type = state["trade_type"]
    tickers = state["candidates"] if trade_type == "medium" else load_nifty500_tickers()
    
    print(f"\n  Running Technical Analysis on {len(tickers) if tickers else 500} stocks...")

    try:
        result = run_technical_analysis.invoke({"trade_type": trade_type, "tickers": tickers, "risk_profile": state["risk"]})

        if isinstance(result, str):
            result = json.loads(result)

        if "error" in result:
            logger.error(f"TA tool error: {result['error']}")
            return state 
        
        ta_stocks     = result.get("stocks", [])
        market_regime = result.get("market_regime", "unknown")
        total_scanned = result.get("total_scanned", 0)

        # Initialize with an empty reason
        reason = ""
        if trade_type == "medium":
            ta_buy_set = {s["ticker"] for s in ta_stocks}
            candidates = [s for s in state["candidates"] if s in ta_buy_set]

            if not candidates:
                # Distinguish scenario: is TA finding NO buys at all, or just
                # no overlap with the FA shortlist?
                if not ta_stocks and market_regime == "bearish":
                    reason = (
                        f"Market regime is BEARISH. No stocks cleared the technical entry threshold (score ≥ 0.60) "
                        f"across all {total_scanned} scanned stocks. This is not a suitable "
                        f"time to enter positions. Consider revisiting in 5–10 trading sessions "
                        f"or when the market trend reverses upward."
                    )
                elif not ta_stocks:
                    reason = (
                        f"No stocks cleared the technical entry threshold (score ≥ 0.60) "
                        f"in a {market_regime} market across {total_scanned} stocks scanned. "
                        f"Wait for clearer setups."
                    )
            
                logger.warning(f"TA abort: {reason}")

        else:  # swing / short
            candidates = [s["ticker"] for s in ta_stocks]

            if not candidates:
                if market_regime == "bearish":
                    reason = (
                        f"Market regime is BEARISH. No {trade_type} trade setups found "
                        f"across {total_scanned} Nifty 500 stocks. Swing and short-term trades "
                        f"carry high risk in a bearish regime. Come back when the market "
                        f"stabilises — typically 5–15 trading sessions."
                    )
                else:
                    reason = (
                        f"No stocks cleared the technical entry threshold."
                        f"No {trade_type} setups available today."
                    )
                logger.warning(f"TA abort: {reason}")

        
        # Normal path — candidates found
        # Sort by TA score descending
        ta_score_map = {s["ticker"]: s.get("score", 0) for s in ta_stocks}
        candidates.sort(key=lambda ticker: ta_score_map.get(ticker, 0), reverse=True)

        return {
                **state,
                "technical_results": ta_stocks,
                "market_regime":     market_regime,
                "candidates":        candidates,
                "abort_reason":      reason,
            }

    except Exception as e:
        logger.error(f"TA node failed: {e}")
        return state
    
def route_after_ta(state: TradingState) -> str:
    """
    Conditional edge after run_ta.
    If TA found no candidates, skip news + decide and go straight
    to the abort report. Otherwise continue normally.
    """
    if state.get("abort_reason"):
        return "abort"
    return "run_news"


# ── Node 4: run_news_node ─────────────────────────────────────────────────────

def run_news_node(state: TradingState) -> TradingState:
    """
    Runs News Sentiment as a fixed graph node.
    Always runs — for all trade types.
    Runs on candidates (TA buy stocks).
    """
    symbols = state["candidates"]

    if not symbols:
        logger.warning("No symbols for news — skipping")
        return state

    logger.info(f"\n  Running News Sentiment for {len(symbols)} stocks...")

    try:
        result = run_news_sentiment.invoke({"symbols": symbols})

        if isinstance(result, str):
            result = json.loads(result)

        news_results = result if isinstance(result, list) else []

        logger.info(f"  News complete: {len(news_results)} records")

        return {**state, "news_results": news_results}

    except Exception as e:
        logger.error(f"News node failed: {e}")
        return state


# ── Node 5: make_final_decision ───────────────────────────────────────────────

def make_final_decision(state: TradingState) -> TradingState:
    """
    For each stock in candidates, make a final BUY/HOLD/SELL decision with reasoning:
      1. Fetch O(1) Macro/Sector/Background Context (ContextBuilder)
      2. Fetch Varsity Trading Rules tailored to the current indicators (Strategy RAG)
      3. Call Groq LLM for reasoning
      4. Parse JSON decision
    """

    # candidates capped at MAX_DECISION_STOCKS
    state["candidates"] = state["candidates"][:MAX_DECISION_STOCKS]
    
    if not state["candidates"]:
        logger.warning("candidates is empty — no decisions to make.")
        return {**state, "decisions": []}

    # ── 1. INITIALIZE DUAL-BRAIN (Runs ONCE per batch) ──
    strategy_rag = _get_strategy_rag()
    context_builder = ContextBuilder()
    context_builder.build(state["candidates"])

    decision_llm = _get_decision_llm()

    fund_idx = {c["ticker"]:         c for c in state["fundamental_results"]}
    tech_idx = {s["ticker"]:         s for s in state["technical_results"]}
    news_idx = { n["matched_symbol"]: n 
                for n in state["news_results"] 
                if "matched_symbol" in n
            }

    if state["trade_type"] == "medium":
        weights = {
            "low":    {"fundamental": 0.60, "technical": 0.20, "news": 0.20},
            "medium": {"fundamental": 0.40, "technical": 0.35, "news": 0.25},
            "high":   {"fundamental": 0.20, "technical": 0.50, "news": 0.30},
        }[state["risk"]]
    else:
        weights = {
            "low":    {"fundamental": 0.00, "technical": 0.60, "news": 0.40},
            "medium": {"fundamental": 0.00, "technical": 0.65, "news": 0.35},
            "high":   {"fundamental": 0.00, "technical": 0.70, "news": 0.30},
        }[state["risk"]]

    decisions        = []
    portfolio_so_far = []
    total_invested   = 0.0

    print(f"\n  Making decisions on {len(state['candidates'])} stocks...\n")

    for symbol in state["candidates"]:
        fund   = fund_idx.get(symbol, {})
        tech   = tech_idx.get(symbol, {})
        news   = news_idx.get(symbol, {})
        sector = tech.get("sector") or fund.get("sector") or "General"

        portfolio_note = (
            "No positions selected yet."
            if not portfolio_so_far
            else "Already selected:\n" + "\n".join(f"  - {s}" for s in portfolio_so_far)
        )

        remaining_capital = max(0.0, state["amount"] - total_invested)

        # Skip remaining stocks if no capital left
        if remaining_capital < 500:  # minimum meaningful position size
            decisions.append({
                "symbol": symbol, "sector": sector, "trade_type": state["trade_type"],
                "action": "HOLD", "confidence": 0.0, "invest_amount": 0,
                "reasoning": "Insufficient remaining capital for a meaningful position.",
                "risk_flags": ["capital exhausted"],
                "signal_agreement": "N/A",
                "breakdown": {
                    "live_price": tech.get("live_price", "N/A"),
                    "fundamental_score": fund.get("score", "N/A"),
                    "fundamental_reasoning": fund.get("reasoning", "N/A"),
                    "technical_score": tech.get("score", "N/A"),
                    "technical_label": tech.get("label", "N/A"),
                    "nearest_support": tech.get("nearest_support", "N/A"),
                    "nearest_resistance": tech.get("nearest_resistance", "N/A"),
                    "news_score": news.get("weighted_score", 0.0),
                    "news_signal": news.get("signal_strength", "N/A"),
                },
            })
            continue

        # ── 1. GET O(1) MACRO CONTEXT ──
        # Returns the 52W range, beta, and sector trend.
        macro_context = context_builder.get_context(symbol, sector)

        # ── 2. SMART VARSITY RAG QUERY ──
        tech_label = tech.get("label", "neutral")
        tech_reasoning = tech.get("reasoning", "")
        is_counter_trend = "⚠ Bearish market" in tech_reasoning

        if state["trade_type"] == "medium":
            # Module 3 Focus: Margin of Safety, ROE, Value + Module 2 Entry timing
            rag_query = f"Fundamental analysis margin of safety qualitative research checklist. Technical entry rules for {tech_label} using {tech_reasoning}"
        else:
            if is_counter_trend:
                # Module 2 Focus: Risk management against the trend
                rag_query = f"Technical analysis trading against the trend, risk management, stop loss rules for {tech_label} in bearish regime."
            else:
                # Module 2 Focus: Trend following, Dow Theory, Volume confirmation
                rag_query = f"Technical analysis swing trading Dow theory trend following. Volume confirmation and support resistance rules for {tech_reasoning} setup."
        
        if hasattr(strategy_rag, 'get_strategy_rules'):
            varsity_rules = strategy_rag.get_strategy_rules(rag_query)
        else:
            varsity_rules = "Follow standard risk management and support/resistance sizing."

        # Risk Management & Psychology Query
        # We query FAISS for position sizing based on the user's specific risk profile, and we fetch psychological checks to prevent AI bias.
        risk_query = (
            f"Position sizing rules, capital allocation, and risk management for a {state['risk']} risk trader. "
            f"Trading psychology: How to avoid confirmation bias and anchoring bias."
        )

        if hasattr(strategy_rag, 'get_strategy_rules'):
            risk_and_psych_rules = strategy_rag.get_strategy_rules(risk_query)
        else:
            risk_and_psych_rules = "Follow strict position sizing. Risk maximum 2% of total capital per trade."

        # ── 1. Fundamental Block ──
        if fund:
            fund_block = (
                f"FUNDAMENTAL (weight {weights['fundamental']*100:.0f}%):\n"
                f"  Score      : {fund.get('score', 'N/A')} / 1.0\n"
                f" Varsity Archetype : {fund.get('archetype', 'Unknown')}\n"
                f"  Sector     : {fund.get('sector', 'General')}\n"
                f"  Reasoning  : {fund.get('reasoning', 'No reasoning provided.')}\n"
            )
        else:
            fund_block = f"FUNDAMENTAL: Not called ({state['trade_type']} trade)"

        # ── 2. Technical Block ──
        if tech:
            tech_block = (
                f"TECHNICAL (weight {weights['technical']*100:.0f}%):\n"
                f"  Score              : {tech.get('score', 'N/A')} / 1.0\n"
                f"  Live Price         : ₹{tech.get('live_price', 'N/A')}\n"
                f"  Label              : {tech.get('label', 'N/A')}\n"
                f"  Market Regime      : {state.get('market_regime', 'N/A')}\n"
                f"  Nearest Support    : {tech.get('nearest_support', 'N/A')}\n"
                f"  Nearest Resistance : {tech.get('nearest_resistance', 'N/A')}\n"
                f"  Support Strength   : {tech.get('support_strength', 'N/A')}\n"
                f"  TA Agent Reasoning : {tech.get('reasoning', 'No reasoning provided.')}\n"
            )
        else:
            tech_block = (
                f"TECHNICAL (weight {weights['technical']*100:.0f}%):\n"
                f"  WARNING: This stock failed the Technical Agent's entry criteria or data is missing.\n"
                f"  Do not invent technical scores. Proceed with extreme caution based ONLY on fundamentals.\n"
            )

        # ── 3. News Sentiment Block ──
        if news:
            news_block = (
                f"NEWS SENTIMENT (weight {weights['news']*100:.0f}%):\n"
                f"  Weighted score  : {news.get('weighted_score', 0.0):.4f}  (-1 to +1)\n"
                f"  Signal          : {news.get('signal_strength', 'N/A')}\n"
                f"  Confidence      : {news.get('g_confidence', 'N/A')}\n"
                f"  Article count   : {news.get('article_count', 0)}\n"
            )
        else:
            news_block = "NEWS SENTIMENT: No recent news found."
        
        # ── 3. VARSITY-ALIGNED DECISION INSTRUCTIONS ──
        if state["trade_type"] == "medium":
            # Varsity Module 3 (Fundamental) + Module 2 (Technical Entry)
            varsity_instructions = f"""
                    DECISION INSTRUCTIONS (Varsity Methodology)
                    1. FUNDAMENTAL DOMINANCE: The 'Varsity Archetype' is your primary filter. 
                        - If the archetype is 'Consistent Wealth Creator' or 'Margin of Safety Play', prioritize for a BUY.
                        - If the archetype is 'Value Trap' or 'Wealth Destroyer', you MUST reject the trade (SELL/HOLD), regardless of how good the technicals look.
                    2. TECHNICAL TIMING: Use the Technical Agent's Support/Resistance purely to optimize the entry price of high-quality fundamentals.
                    3. RAG COMPLIANCE: Cross-reference the FA Reasoning with the ZERODHA VARSITY RULES provided. 
                    4. SIZING: Allocate 10-15% of total capital for a STRONG BUY (Strong Archetype + Technical Support proximity). Allocate 5-8% for a standard BUY.
                    5. REASONING: Your reasoning must explicitly state the 'Varsity Archetype' and explain how the current entry price provides a Margin of Safety.
                    """
        else:
            # Varsity Module 2 (Technical & Momentum)
            varsity_instructions = f"""
                    DECISION INSTRUCTIONS (Varsity Methodology)
                    1. TECHNICAL DOMINANCE: Treat the LIVE AGENT SIGNALS as absolute truth. Fundamentals are irrelevant for this timeframe.
                    2. DOW THEORY & TREND: Prioritize stocks showing strong momentum aligned with the Market Regime. If the 'TA Agent Reasoning' indicates a counter-trend setup (e.g., Bearish Market), you MUST strictly reduce position size or reject the trade.
                    3. VOLUME & INDICATOR CONFIRMATION: Rely on the TA Agent Reasoning (RSI, MACD, EMAs, etc) to confirm the strength of the move. 
                    4. RISK/REWARD: You MUST calculate a logical Risk/Reward ratio using the Current Price ₹{tech.get('live_price')}, Nearest Support (Stop Loss), and Nearest Resistance (Target). If the Reward is not at least 1.5x the Risk, reject the trade.
                    5. SIZING: Allocate 10-15% of total capital for a STRONG BUY (High Conviction Technical Setup + Favorable Risk/Reward). Allocate 5-8% for a standard BUY.
                    """
        
        # ── 4. Hard sector cap: max 2 stocks per sector in final portfolio ──
        sector_counts = {}
        for entry in portfolio_so_far:
            sec = entry.split("[")[1].split("]")[0] if "[" in entry else "General"
            sector_counts[sec] = sector_counts.get(sec, 0) + 1

        if sector_counts.get(sector, 0) >= 2:
            logger.info(f"Skipping {symbol} — sector '{sector}' already has 2 positions")
            decisions.append({
                "symbol": symbol, "sector": sector, "trade_type": state["trade_type"],
                "action": "HOLD", "confidence": 0.0, "invest_amount": 0,
                "reasoning": f"Sector cap reached — {sector} already has 2 positions in portfolio.",
                "risk_flags": ["sector concentration limit"],
                "signal_agreement": "N/A",
                "breakdown": {
                    "live_price": tech.get("live_price", "N/A"),
                    "fundamental_score": fund.get("score", "N/A"),
                    "fundamental_reasoning": fund.get("reasoning", "N/A"),
                    "technical_score": tech.get("score", "N/A"),
                    "technical_label": tech.get("label", "N/A"),
                    "nearest_support": tech.get("nearest_support", "N/A"),
                    "nearest_resistance": tech.get("nearest_resistance", "N/A"),
                    "news_score": news.get("weighted_score", 0.0),
                    "news_signal": news.get("signal_strength", "N/A"),
                },
            })
            continue

        # ── 5. THE LLM PROMPT ──
        prompt = f"""You are an expert Indian stock market quantitative analyst adhering to the principles of Zerodha Varsity.
                USER PROFILE
                Capital remaining : ₹{remaining_capital:,.2f}  (of ₹{state['amount']:,.2f} total)
                Risk              : {state['risk'].upper()}
                Trade type        : {state['trade_type'].upper()}

                # MARKET REGIME & ENTRY TRIGGERS:
                If the broader market is Bearish, so you must be cautious. HOWEVER, if a stock presents a high-conviction Candlestick Reversal pattern (like a Morning Star or Bullish Engulfing) directly at a Support level, you are authorized to approve it as a counter-trend relief rally trade.

                VARSITY ENTRY TRIGGERS:
                Look at the 'candlestick_pattern' in the Technical Data. 
                - If the trade is SWING or SHORT, and a high-conviction reversal pattern is present (e.g., Morning Star, Engulfing) AT support, this is a Grade-A entry. You should explicitly cite this pattern in your reasoning.
                - If the 'candlestick_pattern' says 'N/A', do not attempt to guess the daily price action. Base your decision entirely on the structural trend (EMAs) and Fundamentals.

                {macro_context}

                LIVE AGENT SIGNALS - {symbol} [{sector}]
                {fund_block}
                {tech_block}
                {news_block}

                ZERODHA VARSITY TRADING RULES
                {varsity_rules}

                VARSITY RISK & PSYCHOLOGY RULES
                {risk_and_psych_rules}

                CURRENT PORTFOLIO
                {portfolio_note}

                {varsity_instructions}

                ADDITIONAL RISK & PSYCHOLOGY INSTRUCTIONS (MODULE 9):
                1. DYNAMIC POSITION SIZING: Do NOT use generic 10% allocations. You must read the 'VARSITY RISK RULES' provided above and size this position exactly according to those guidelines based on the Support/Resistance stop-loss distance.
                2. PORTFOLIO VARIANCE: Review the 'CURRENT PORTFOLIO'. If you are already holding stocks in the [{sector}] sector, Varsity warns against high covariance risk. You must reduce the invest_amount or reject the trade to maintain diversification.
                3. PSYCHOLOGICAL AUDIT: Before confirming a BUY, actively check yourself for Confirmation Bias. Are you ignoring a poor Fundamental score just because the MACD is bullish? If the signals are 'CONFLICTED', default to capital preservation (HOLD).

                Reply ONLY with a raw, valid JSON object. Do not include markdown formatting (like ```json), do not include introductory text:
                {{
                "action":           "STRONG BUY | BUY | HOLD | SELL | STRONG SELL",
                "confidence":       <float 0.0-1.0>,
                "invest_amount":    0,
                "reasoning":        "<string summarizing why (2-3 sentences only), citing the specific agent scores, support levels, and Varsity rules for {symbol}>",
                "risk_flags":       ["concerns specific to {symbol}"],
                "signal_agreement": "ALIGNED | MIXED | CONFLICTED"
                }}"""


        print(f"    {symbol}  [{sector}] ...")

        try:
            resp = decision_llm.invoke([HumanMessage(content=prompt)])
            result = json.loads(resp.content)

            invest = min(float(result.get("invest_amount", 0)), remaining_capital)
            result["invest_amount"] = round(invest, 2)

        except Exception as e:
            logger.warning(f"Decision engine error for {symbol}: {e}")
            result = {
                "action":           "HOLD",
                "confidence":       0.0,
                "invest_amount":    0,
                "reasoning":        f"Parse error: {e}",
                "risk_flags":       ["decision engine error"],
                "signal_agreement": "MIXED",
            }

        decisions.append({
            "symbol":     symbol,
            "sector":     sector,
            "trade_type": state["trade_type"],
            **result,
            "breakdown": {
                "live_price":            tech.get("live_price",         "N/A"),
                "fundamental_score":     fund.get("score",              "N/A"),
                "fundamental_reasoning": fund.get("reasoning",          "N/A"),
                "technical_score":       tech.get("score",              "N/A"),
                "technical_label":       tech.get("label",              "N/A"),
                "nearest_support":       tech.get("nearest_support",    "N/A"),
                "nearest_resistance":    tech.get("nearest_resistance", "N/A"),
                "news_score":            news.get("weighted_score",     0.0),
                "news_signal":           news.get("signal_strength",    "N/A"),
            },
        })

        if "BUY" in result.get("action", ""):
            total_invested += result.get("invest_amount", 0)
            portfolio_so_far.append(
                f"{symbol} [{sector}] -> {result['action']}  "
                f"₹{result.get('invest_amount', 0):,.0f}"
            )

    decisions.sort(key=lambda d: d["confidence"], reverse=True)
    return {**state, "decisions": decisions}


# ── Node 6: print_report ──────────────────────────────────────────────────────

def print_report(state: TradingState) -> TradingState:
    decisions    = state["decisions"]
    buys         = [d for d in decisions if "BUY" in d.get("action", "")]
    total_deploy = sum(d.get("invest_amount", 0) for d in buys)

    print("\n" + "=" * 65)
    print(f"  FA screened    : {len(state['fundamental_results'])} candidates passed to TA")
    print(f"  TA approved    : {len(state['technical_results'])} buy signals found")
    print(f"  Sent to LLM    : {len(state['candidates'])} stocks (capped at {MAX_DECISION_STOCKS})")
    print(f"  LLM bought     : {len(buys)} positions")
    
    print("=" * 65)

    print("             FINAL INVESTMENT REPORT")
    print("=" * 65)
    print(f"  Trade type     : {state['trade_type'].upper()}")
    print(f"  Market regime  : {state['market_regime'].upper()}")
    print(f"  Capital        : ₹{state['amount']:,.2f}")
    print(f"  Risk           : {state['risk'].upper()}")
    print(f"  Stocks to buy  : {len(buys)}")
    print(f"  Deploying      : ₹{total_deploy:,.2f}")
    print(f"  Cash reserved  : ₹{state['amount'] - total_deploy:,.2f}")
    print("=" * 65)

    if buys:
        print("\n  BUY DECISIONS")
        print("-" * 65)
    for d in decisions:
        if "BUY" not in d.get("action", ""):
            continue
        bd    = d.get("breakdown", {})
        flags = " | ".join(d.get("risk_flags", [])) or "none"
        print(f"\n  {d['action']:<13}  {d['symbol']:<12}  [{d['sector']}]")
        print(f"  Confidence   : {d['confidence']:.0%}")
        print(f"  Invest       : ₹{d.get('invest_amount', 0):,.2f}")
        print(f"  Agreement    : {d.get('signal_agreement', '')}")
        print(f"  Risk flags   : {flags}")
        print(f"  -- breakdown --")
        
        if bd.get("fundamental_score") != "N/A":
            print(f"    Fundamental  : {bd['fundamental_score']}")
        
        print(f"    Technical    : {bd['technical_score']}  ({bd['technical_label']})")
        print(f"    Support      : {bd['nearest_support']}  "f"Resistance: {bd['nearest_resistance']}")
        
        live_price = bd.get("live_price")
        support    = bd.get("nearest_support")
        if live_price and support and support != "N/A":
            sl_pct = round((live_price - support) / live_price * 100, 1)
            print(f"    Stop-loss    : ₹{support}  ({sl_pct}% downside risk)")
        
        print(f"    News         : {bd['news_score']:.4f}  ({bd['news_signal']})")
        print(f"  Reasoning    : {d.get('reasoning', '')}")

    print("\n  HOLD / AVOID")
    print("-" * 65)
    for d in decisions:
        if "BUY" in d.get("action", ""):
            continue
        print(f"  {d['action']:<13}  {d['symbol']:<12}  "
              f"conf {d['confidence']:.0%}  --  "
              f"{d.get('reasoning', '')[:70]}")

    print("\n" + "=" * 65)
    return state

# ────── Node 7: no_opportunity_report ─────────────────────────────────────────────────
def no_opportunity_report(state: TradingState) -> TradingState:
    """
    Runs when TA aborts with no candidates.
    Uses the LLM to produce a brief, helpful message based on
    the abort reason and market regime.
    This is intentionally simple — one LLM call, no RAG.
    """
    decision_llm = _get_decision_llm()

    prompt = f"""You are a stock market advisor for Indian equity markets.

            The automated analysis system ran for a {state['trade_type'].upper()} trade 
            (capital: ₹{state['amount']:,.2f}, risk: {state['risk'].upper()}) 
            and found NO actionable opportunities.

            Reason from the analysis system:
            {state['abort_reason']}

            Market regime detected: {state['market_regime'].upper()}

            Write a brief, professional message to the investor (2-3 sentences max).
            - Confirm there are no recommendations today.
            - Give one concrete, specific piece of advice about what market condition 
              to watch for before trying again.
            - Suggest a realistic timeframe to check back.
            - Do NOT use generic filler phrases. Be specific to the regime and trade type.

            Respond in plain text only — no JSON, no bullet points, no markdown."""

    try:
        resp = decision_llm.invoke([HumanMessage(content=prompt)])
        message = resp.content.strip()
    except Exception as e:
        logger.warning(f"Abort LLM failed: {e}")
        message = state["abort_reason"]

    print("\n" + "=" * 65)
    print("             ANALYSIS COMPLETE — NO TRADES TODAY")
    print("=" * 65)
    print(f"\n  Trade type  : {state['trade_type'].upper()}")
    print(f"  Risk        : {state['risk'].upper()}")
    print(f"  Regime      : {state['market_regime'].upper()}")
    print(f"  Capital     : ₹{state['amount']:,.2f}  (fully preserved)\n")
    print(f"  {message}\n")
    print("=" * 65)

    return {**state, "decisions": []}


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(TradingState)

    g.add_node("collect_input", collect_user_input)
    g.add_node("run_fa",        run_fa_node)
    g.add_node("run_ta",        run_ta_node)
    g.add_node("run_news",      run_news_node)
    g.add_node("decide",        make_final_decision)
    g.add_node("report",        print_report)
    g.add_node("abort",         no_opportunity_report)

    g.set_entry_point("collect_input")
    g.add_edge("collect_input", "run_fa")
    g.add_edge("run_fa",        "run_ta")

    # Conditional edge replaces the fixed run_ta → run_news edge
    g.add_conditional_edges(
        "run_ta",
        route_after_ta,
        {"run_news": "run_news", "abort": "abort"}
    )

    g.add_edge("run_news", "decide")
    g.add_edge("decide",   "report")
    g.add_edge("report",   END)
    g.add_edge("abort",    END)

    return g.compile()


def run_trading_platform():
    from dotenv import load_dotenv
    load_dotenv()
    build_graph().invoke({
        "amount":              0.0,
        "risk":                "",
        "trade_type":          "",
        "fundamental_results": [],
        "technical_results":   [],
        "news_results":        [],
        "market_regime":       "unknown",
        "candidates":          [],
        "decisions":           [],
        "abort_reason":        "",
    })