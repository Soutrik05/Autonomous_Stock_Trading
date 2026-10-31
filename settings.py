"""
Single source of truth for all constants: capital, costs, rate limits, schedule, order rules,
prompt budgets, funnel and learning thresholds.
See Plan_v3 §Settings.
"""
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

# Ensure 'src' directory is in sys.path for all modules and scripts
_SRC_DIR = Path(__file__).resolve().parent / "src"
if _SRC_DIR.is_dir() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

load_dotenv()  # loads .env into the environment once; safe to call even if .env is absent


@dataclass(frozen=True)
class Settings:
    # --- Secrets (read from environment only; never hard-coded) ---
    UPSTOX_ANALYTICS_TOKEN: str = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "")
    GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")

    # --- Capital and costs (§4.1, Settings Specification) ---
    INITIAL_CASH_PER_AGENT_PAISE: int = 10_000_000
    SLIPPAGE_BPS: int = 10
    STT_RATE: float = 0.001
    EXCHANGE_TURNOVER_RATE: float = 0.0000297
    SEBI_FEE_RATE: float = 0.000001
    STAMP_DUTY_RATE: float = 0.00015
    GST_RATE: float = 0.18
    DP_CHARGES_PAISE: int = 1534
    BROKERAGE_PAISE: int = 0

    # --- Rate limits (§1.3) ---
    RATE_LIMIT_PER_SEC: int = 45
    RATE_LIMIT_PER_MIN: int = 450
    RATE_LIMIT_PER_30MIN: int = 1800

    # --- Schedule, all times IST (§1.4) ---
    INGESTION_TIME: str = "20:00"
    BACKUP_TIME: str = "21:45"
    AGENT_RUN_TIME: str = "22:00"
    MONITOR_START: str = "09:20"
    MONITOR_END: str = "15:20"
    MONITOR_INTERVAL_MIN: int = 10
    EXPIRY_TIME: str = "15:30"
    SETTLEMENT_TIME: str = "15:35"
    FORWARD_RETURN_BACKFILL_TIME: str = "15:45"
    REFLECTION_DAY: str = "Sunday"
    REFLECTION_TIME: str = "10:00"
    MACRO_NARRATIVE_DAYS: str = "1,15"
    MACRO_NARRATIVE_TIME: str = "09:30"

    # --- Orders (§4.3) ---
    BUY_OVERSHOOT_PCT: float = 0.5
    STOP_MAY_ONLY_RISE: bool = True
    MAX_OPEN_POSITIONS_PER_AGENT: int = 5
    # How valid_for_date is chosen for a new pending order (day 4a). NEXT_TRADING_DAY matches
    # Plan_v3 §4.3 item 1 literally; SAME_DAY_IF_BEFORE_OPEN is the alternative the task asks
    # the broker to also support.
    ORDER_VALIDITY_MODE: str = os.environ.get("ORDER_VALIDITY_MODE", "NEXT_TRADING_DAY")
    MARKET_OPEN_TIME: str = "09:15"  # cutoff for ORDER_VALIDITY_MODE=SAME_DAY_IF_BEFORE_OPEN

    # --- Broker soft caps (§4.2; non-blocking, logged as CAP_BREACH) (day 4a) ---
    MAX_RISK_PCT_PER_TRADE: float = 2.0
    MAX_POSITION_PCT_OF_ACCOUNT: float = 20.0
    MAX_SECTOR_PCT_OF_ACCOUNT: float = 25.0

    # --- LLM providers (§3.2) ---
    LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "gemini")
    LLM_MODEL: str = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
    LLM_FALLBACK_PROVIDER: str = os.environ.get("LLM_FALLBACK_PROVIDER", "groq")
    LLM_FALLBACK_MODEL: str = os.environ.get("LLM_FALLBACK_MODEL", "llama-3.3-70b-versatile")
    LLM_REASONING_EFFORT: str = os.environ.get("LLM_REASONING_EFFORT", "low")
    LLM_MAX_OUTPUT_TOKENS: int = int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "4000"))
    LLM_TEMPERATURE: float = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
    # 0 = thinking off, -1 = dynamic/model-chosen budget, >0 = a fixed token budget (Gemini only).
    LLM_GEMINI_THINKING_BUDGET: int = int(os.environ.get("LLM_GEMINI_THINKING_BUDGET", "1024"))

    # --- Reflection LLM providers ---
    REFLECTION_LLM_PROVIDER: str = os.environ.get("REFLECTION_LLM_PROVIDER", "gemini")
    REFLECTION_LLM_MODEL: str = os.environ.get("REFLECTION_LLM_MODEL", "gemini-3.8-flash")
    REFLECTION_LLM_FALLBACK_PROVIDER: str = os.environ.get("REFLECTION_LLM_FALLBACK_PROVIDER", "groq")
    REFLECTION_LLM_FALLBACK_MODEL: str = os.environ.get("REFLECTION_LLM_FALLBACK_MODEL", "openai/gpt-oss-120b")

    # --- Prompts (§3.2) ---
    MAX_CANDIDATES_PER_RUN: int = 10
    AGENT_RUN_DELAY_SEC: int = 60
    PROMPT_TOKEN_TARGET: int = 2800
    PROMPT_TOKEN_CEILING: int = 3800
    EPISODIC_MEMORY_LIMIT: int = 10
    MIN_CITED_METRICS: int = 3

    # --- Funnel (§6) ---
    MIN_SECTOR_COHORT: int = 8
    SECTOR_PERCENTILE_MIN: float = 0
    SECTOR_CAP_PER_AGENT: int = 2
    WATCHLIST_TARGET_SIZE_MIN: int = 8
    WATCHLIST_TARGET_SIZE_MAX: int = 10
    MIN_TURNOVER_RUPEES: int = 50_000_000

    # --- Learning (§5) ---
    MIN_CLOSED_TRADES_FOR_REFLECTION: int = 3
    FORWARD_HORIZONS: List[int] = field(default_factory=lambda: [1, 5, 8, 10, 20, 60, 90, 120])
    HEURISTIC_ACTIVE_MIN_APPLICATIONS: int = 3
    HEURISTIC_ACTIVE_MIN_SUCCESS_RATE: float = 0.6
    HEURISTIC_REINFORCED_MIN_APPLICATIONS: int = 10
    HEURISTIC_REINFORCED_MIN_SUCCESS_RATE: float = 0.6
    HEURISTIC_DEPRECATED_MAX_SUCCESS_RATE: float = 0.4
    HEURISTIC_DEPRECATED_MIN_APPLICATIONS: int = 3
    HEURISTIC_DEPRECATED_STALE_DAYS: int = 30
    MAX_ACTIVE_HEURISTICS_IN_PROMPT: int = 5

    # --- Data & corporate actions (§1.5, §2.5) ---
    CORP_ACTION_DIFF_PCT: float = 5.0
    CORP_ACTION_LOOKBACK_CANDLES: int = 10
    INGESTION_RETRY_COUNT: int = 3
    OHLCV_BACKFILL_DAYS: int = 400
    MARKET_QUOTE_BATCH_SIZE: int = 500
    VIX_BANDS: Dict[str, float] = field(
        default_factory=lambda: {"LOW_VOL": 14.0, "NORMAL": 18.0, "ELEVATED": 24.0}
    )

    # --- Paths ---
    TIMEZONE: str = "Asia/Kolkata"
    PORTFOLIO_DB_PATH: str = os.environ.get("PORTFOLIO_DB_PATH", "storage/ledger/portfolio.db")
    MARKET_DB_DIR: str = os.environ.get("MARKET_DB_DIR", "storage/market")
    OHLCV_DB_PATH: str = os.environ.get("OHLCV_DB_PATH", "storage/market/ohlcv.db")
    MACRO_DB_PATH: str = os.environ.get("MACRO_DB_PATH", "storage/market/macro.db")
    FUNDAMENTAL_DB_PATH: str = os.environ.get("FUNDAMENTAL_DB_PATH", "storage/market/fundamental.db")
    NEWS_DB_PATH: str = os.environ.get("NEWS_DB_PATH", "storage/market/news.db")
    BACKUP_DIR: str = os.environ.get("BACKUP_DIR", "backups")
    FUNDAMENTAL_REFETCH_DAYS: int = 14
    DB_BUSY_TIMEOUT_MS: int = 5000
    UPSTOX_BASE_URL: str = "https://api.upstox.com"


settings = Settings()
