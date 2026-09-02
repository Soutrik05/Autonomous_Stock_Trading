# ============================================================
# fundamental_agent/__init__.py
#
# Public API for the fundamental_agent package.
# The only symbol the rest of the project needs to import is
# run_fundamental_analysis — the LangChain @tool.
#
# Usage from anywhere in the project:
#   from fundamental_agent import run_fundamental_analysis
#   results = run_fundamental_analysis.invoke({"tickers": ["TCS", "RELIANCE"]})
# ============================================================

from fundamental_agent.agent import run_fundamental_analysis

__all__ = ["run_fundamental_analysis"]
