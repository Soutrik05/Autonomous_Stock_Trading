"""
Single source of truth for all constants: capital, costs, rate limits, schedule, order rules,
prompt budgets, funnel and learning thresholds.
See Plan_v3 §Settings.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List


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

    # --- Learning (§5) ---
    MIN_CLOSED_TRADES_FOR_REFLECTION: int = 3
    FORWARD_HORIZONS: List[int] = field(default_factory=lambda: [1, 5, 10, 20])
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
    VIX_BANDS: Dict[str, float] = field(
        default_factory=lambda: {"LOW_VOL": 14.0, "NORMAL": 18.0, "ELEVATED": 24.0}
    )

    # --- Paths ---
    TIMEZONE: str = "Asia/Kolkata"
    PORTFOLIO_DB_PATH: str = os.environ.get("PORTFOLIO_DB_PATH", "state/portfolio.db")
    MARKET_DB_DIR: str = os.environ.get("MARKET_DB_DIR", "data")
    DB_BUSY_TIMEOUT_MS: int = 5000


settings = Settings()
