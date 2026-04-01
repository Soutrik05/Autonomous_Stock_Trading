# =============================================================================
# orchestrator/graph.py
#
# LangGraph orchestrator — the single brain of the trading platform.
#
# ARCHITECTURE:
#   All three agents run as FIXED graph nodes — no LLM involvement.
#   LLM is only used in make_final_decision for per-stock reasoning.
#
# FLOW:
#   MEDIUM : collect_input → run_fa → run_ta (top 20) → run_news → decide → report
#   SWING  : collect_input → run_fa (skip) → run_ta (500) → run_news → decide → report
#   SHORT  : collect_input → run_fa (skip) → run_ta (500) → run_news → decide → report
# =============================================================================

import json
import os
import logging
from typing import Annotated, TypedDict

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from orchestrator.rag.retriever import Retriever
from fundamental_agent.agent import run_fundamental_analysis
from technical_agent.agent   import run_technical_analysis
from news_sentiment.tool     import run_news_sentiment

logger = logging.getLogger(__name__)

_agent_llm    = None
_decision_llm = None

def _get_llms():
    global _agent_llm, _decision_llm
    if _agent_llm is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise EnvironmentError("GROQ_API_KEY not set — check your .env file.")
        _agent_llm    = ChatGroq(model="llama-3.3-70b-versatile", temperature=0,   api_key=key)
        _decision_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1, api_key=key)
        logger.info("ChatGroq instances initialised (llama-3.3-70b-versatile)")
    return _agent_llm, _decision_llm


# ── State ─────────────────────────────────────────────────────────────────────

class TradingState(TypedDict):
    amount:              float
    risk:                str
    trade_type:          str
    messages:            Annotated[list, "messages"]
    fundamental_results: list
    technical_results:   list
    news_results:        list
    market_regime:       str
    top_symbols:         list
    decisions:           list


# ── Node 1: collect_user_input ────────────────────────────────────────────────

def collect_user_input(state: TradingState) -> TradingState:
    print("\n" + "=" * 62)
    print("          AUTONOMOUS TRADING PLATFORM")
    print("=" * 62)

    amount = float(input("\n💰  How much do you want to invest? (₹): "))

    print("\n📊  Risk Appetite:")
    print("    1. Low    — capital preservation priority")
    print("    2. Medium — balanced risk / reward")
    print("    3. High   — aggressive, momentum driven")
    risk = {"1": "low", "2": "medium", "3": "high"}.get(
        input("\n    Choose (1/2/3): ").strip(), "medium"
    )

    print("\n📈  Trade Type:")
    print("    1. Medium  (3-6 months)  -> Fundamental + Technical + News")
    print("    2. Short   (2-8 weeks)   -> Technical + News only")
    print("    3. Swing   (2-10 days)   -> Technical + News only")
    trade_type = {"1": "medium", "2": "short", "3": "swing"}.get(
        input("\n    Choose (1/2/3): ").strip(), "swing"
    )

    print(f"\n✅  ₹{amount:,.2f}  |  {risk.upper()} risk  |  {trade_type.upper()} trade\n")

    return {
        **state,
        "amount":              amount,
        "risk":                risk,
        "trade_type":          trade_type,
        "messages":            [SystemMessage(content="Trading platform started.")],
        "fundamental_results": [],
        "technical_results":   [],
        "news_results":        [],
        "market_regime":       "unknown",
        "top_symbols":         [],
        "decisions":           [],
    }


# ── Node 2: run_fa_node ───────────────────────────────────────────────────────

def run_fa_node(state: TradingState) -> TradingState:
    """
    Runs Fundamental Analysis as a fixed graph node.
    Only runs for MEDIUM trades. Skipped for swing/short.
    Returns top 20 candidates for TA to analyse.
    """
    if state["trade_type"] != "medium":
        logger.info("FA skipped — not a medium trade")
        return state

    print("\n⏳  Running Fundamental Analysis on 501 stocks...")
    print("    (takes ~1 minute with 20 parallel workers)\n")

    try:
        result = run_fundamental_analysis.invoke({"tickers": []})

        if isinstance(result, str):
            result = json.loads(result)

        candidates  = result.get("candidates", [])[:20]
        top_symbols = [c["ticker"] for c in candidates]

        print(f"✅  FA complete: {len(candidates)} candidates selected")
        logger.info(f"FA: {len(candidates)} candidates | top_symbols={top_symbols}")

        return {
            **state,
            "fundamental_results": candidates,
            "top_symbols":         top_symbols,
        }

    except Exception as e:
        logger.error(f"FA node failed: {e}")
        return state


# ── Node 3: run_ta_node ───────────────────────────────────────────────────────

def run_ta_node(state: TradingState) -> TradingState:
    """
    Runs Technical Analysis as a fixed graph node.
    MEDIUM : runs on FA top 20 symbols
    SWING/SHORT : runs on full Nifty 500
    Always runs — for all trade types.
    """
    trade_type = state["trade_type"]

    if trade_type == "medium":
        tickers = state["top_symbols"]
        if not tickers:
            logger.warning("FA returned no candidates — skipping TA")
            return state
        print(f"\n⏳  Running Technical Analysis on {len(tickers)} FA candidates...")
    else:
        tickers = None
        print(f"\n⏳  Running Technical Analysis on full Nifty 500...")
        print("    (takes ~7 minutes)")

    try:
        result = run_technical_analysis.invoke({
            "trade_type": trade_type,
            "tickers":    tickers,
        })

        if isinstance(result, str):
            result = json.loads(result)

        ta_stocks     = result.get("stocks", [])
        market_regime = result.get("market_regime", "unknown")

        if trade_type == "medium":
            ta_buy_set  = {s["ticker"] for s in ta_stocks}
            top_symbols = [s for s in state["top_symbols"] if s in ta_buy_set]
            if not top_symbols:
                logger.warning("TA found no buys from FA list — using FA list directly")
                top_symbols = state["top_symbols"]
        else:
            top_symbols = [s["ticker"] for s in ta_stocks]

        print(f"✅  TA complete: {len(ta_stocks)} buy signals | regime={market_regime}")
        logger.info(f"TA: {len(ta_stocks)} buy stocks | regime={market_regime} | top_symbols={len(top_symbols)}")

        return {
            **state,
            "technical_results": ta_stocks,
            "market_regime":     market_regime,
            "top_symbols":       top_symbols,
        }

    except Exception as e:
        logger.error(f"TA node failed: {e}")
        return state


# ── Node 4: run_news_node ─────────────────────────────────────────────────────

def run_news_node(state: TradingState) -> TradingState:
    """
    Runs News Sentiment as a fixed graph node.
    Always runs — for all trade types.
    Runs on top_symbols (TA buy stocks).
    """
    symbols = state["top_symbols"]

    if not symbols:
        logger.warning("No symbols for news — skipping")
        return state

    print(f"\n⏳  Running News Sentiment for {len(symbols)} stocks...")

    try:
        result = run_news_sentiment.invoke({
            "symbols_json": json.dumps(symbols)
        })

        if isinstance(result, str):
            result = json.loads(result)

        news_results = result if isinstance(result, list) else []

        print(f"✅  News complete: {len(news_results)} records")
        logger.info(f"News: {len(news_results)} records")

        return {**state, "news_results": news_results}

    except Exception as e:
        logger.error(f"News node failed: {e}")
        return state


# ── Node 5: make_final_decision ───────────────────────────────────────────────

def make_final_decision(state: TradingState) -> TradingState:
    """
    For each stock in top_symbols:
      1. Fetch RAG context
      2. Build prompt with all agent signals
      3. Call Groq LLM for reasoning
      4. Parse JSON decision
    This is the ONLY place LLM is used.
    """
    if not state["top_symbols"]:
        logger.warning("top_symbols is empty — no decisions to make.")
        return {**state, "decisions": []}

    retriever       = Retriever()
    _, decision_llm = _get_llms()

    fund_idx = {c["ticker"]:         c for c in state["fundamental_results"]}
    tech_idx = {s["ticker"]:         s for s in state["technical_results"]}
    news_idx = {n["matched_symbol"]: n for n in state["news_results"]}

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

    print(f"\n⏳  Making decisions on {len(state['top_symbols'])} stocks...\n")

    for symbol in state["top_symbols"]:
        fund   = fund_idx.get(symbol, {})
        tech   = tech_idx.get(symbol, {})
        news   = news_idx.get(symbol, {})
        sector = tech.get("sector") or fund.get("sector") or "General"

        rag_context = retriever.get_context_for_stock(symbol, sector)

        portfolio_note = (
            "No positions selected yet."
            if not portfolio_so_far
            else "Already selected:\n" + "\n".join(f"  - {s}" for s in portfolio_so_far)
        )

        remaining_capital = state["amount"] - total_invested

        if fund:
            fund_block = (
                f"FUNDAMENTAL (weight {weights['fundamental']*100:.0f}%):\n"
                f"  Score     : {fund.get('score', 'N/A')} / 1.0\n"
                f"  Reasoning : {fund.get('reasoning', 'N/A')}"
            )
        else:
            fund_block = f"FUNDAMENTAL: not called ({state['trade_type']} trade)"

        tech_block = (
            f"TECHNICAL (weight {weights['technical']*100:.0f}%):\n"
            f"  Score              : {tech.get('score', 'N/A')} / 1.0\n"
            f"  Label              : {tech.get('label', 'N/A')}\n"
            f"  Nearest support    : {tech.get('nearest_support', 'N/A')}\n"
            f"  Nearest resistance : {tech.get('nearest_resistance', 'N/A')}\n"
            f"  Support strength   : {tech.get('support_strength', 'N/A')}\n"
            f"  Market regime      : {state['market_regime']}\n"
            f"  Reasoning          : {tech.get('reasoning', 'N/A')}"
        )

        news_block = (
            f"NEWS SENTIMENT (weight {weights['news']*100:.0f}%):\n"
            f"  Weighted score  : {news.get('weighted_score', 0.0):.4f}  (-1 to +1)\n"
            f"  Signal          : {news.get('signal_strength', 'N/A')}\n"
            f"  Confidence      : {news.get('g_confidence', 'N/A')}\n"
            f"  Article count   : {news.get('article_count', 0)}"
        )

        prompt = f"""You are an expert Indian stock market analyst making real investment decisions.

USER PROFILE
  Capital remaining : ₹{remaining_capital:,.2f}  (of ₹{state['amount']:,.2f} total)
  Risk              : {state['risk'].upper()}
  Trade type        : {state['trade_type'].upper()}

REAL MARKET CONTEXT (from RAG knowledge base)
{rag_context}

LIVE AGENT SIGNALS - {symbol}  [{sector}]
{fund_block}

{tech_block}

{news_block}

CURRENT PORTFOLIO
{portfolio_note}

DECISION INSTRUCTIONS
1. Analyse THIS stock ({symbol}) specifically — do not mix up with other stocks.
2. Cross-reference RAG data with agent signals — flag conflicts explicitly.
3. Medium: weight fundamentals heavily, technicals confirm entry timing.
4. Swing/Short: focus on technical setup, news is a risk filter.
5. Use support/resistance for position sizing.
6. Avoid sector concentration — check portfolio above.
7. invest_amount must be between 0 and ₹{remaining_capital:,.2f}.
   STRONG BUY = 10-15% of ₹{state['amount']:,.2f}
   BUY = 5-8% of ₹{state['amount']:,.2f}
   HOLD/SELL = 0

Reply with ONLY valid JSON — no markdown, no extra text:
{{
  "action":           "STRONG BUY | BUY | HOLD | SELL | STRONG SELL",
  "confidence":       0.0,
  "invest_amount":    0,
  "reasoning":        "2-3 sentences specifically about {symbol}",
  "risk_flags":       ["concerns specific to {symbol}"],
  "signal_agreement": "ALIGNED | MIXED | CONFLICTED"
}}"""

        print(f"  🤖  {symbol}  [{sector}] ...")

        try:
            resp = decision_llm.invoke([HumanMessage(content=prompt)])
            raw  = resp.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())

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
                "fundamental_score":     fund.get("score",              "N/A"),
                "fundamental_reasoning": fund.get("reasoning",          "N/A"),
                "technical_score":       tech.get("score",              "N/A"),
                "technical_label":       tech.get("label",              "N/A"),
                "nearest_support":       tech.get("nearest_support",    "N/A"),
                "nearest_resistance":    tech.get("nearest_resistance", "N/A"),
                "news_score":            news.get("weighted_score",     0.0),
                "news_signal":           news.get("signal_strength",    "N/A"),
                "market_regime":         state["market_regime"],
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
        print("\n🟢  BUY DECISIONS")
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
        print(f"  Reasoning    : {d.get('reasoning', '')}")
        print(f"  Risk flags   : {flags}")
        print(f"  -- breakdown --")
        if bd.get("fundamental_score") != "N/A":
            print(f"    Fundamental  : {bd['fundamental_score']}")
        print(f"    Technical    : {bd['technical_score']}  ({bd['technical_label']})")
        print(f"    Support      : {bd['nearest_support']}  "
              f"Resistance: {bd['nearest_resistance']}")
        print(f"    News         : {bd['news_score']:.4f}  ({bd['news_signal']})")
        print(f"    Regime       : {bd['market_regime']}")

    print("\n🟡  HOLD / AVOID")
    print("-" * 65)
    for d in decisions:
        if "BUY" in d.get("action", ""):
            continue
        print(f"  {d['action']:<13}  {d['symbol']:<12}  "
              f"conf {d['confidence']:.0%}  --  "
              f"{d.get('reasoning', '')[:70]}")

    print("\n" + "=" * 65)
    return state


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(TradingState)

    g.add_node("collect_input", collect_user_input)
    g.add_node("run_fa",        run_fa_node)
    g.add_node("run_ta",        run_ta_node)
    g.add_node("run_news",      run_news_node)
    g.add_node("decide",        make_final_decision)
    g.add_node("report",        print_report)

    g.set_entry_point("collect_input")
    g.add_edge("collect_input", "run_fa")
    g.add_edge("run_fa",        "run_ta")
    g.add_edge("run_ta",        "run_news")
    g.add_edge("run_news",      "decide")
    g.add_edge("decide",        "report")
    g.add_edge("report",        END)

    return g.compile()


def run_trading_platform():
    from dotenv import load_dotenv
    load_dotenv()
    build_graph().invoke({
        "amount":              0.0,
        "risk":                "",
        "trade_type":          "",
        "messages":            [],
        "fundamental_results": [],
        "technical_results":   [],
        "news_results":        [],
        "market_regime":       "unknown",
        "top_symbols":         [],
        "decisions":           [],
    })