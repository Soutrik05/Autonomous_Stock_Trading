"""
Configuration Management for StockMinds.
Uses Pydantic v2 BaseSettings for type-safe environment variable parsing,
validation, and default settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # --- Secrets (read from environment only; never hard-coded) ---
    UPSTOX_ANALYTICS_TOKEN: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    # --- Capital and costs (§4.1, Settings Specification) ---
    INITIAL_CASH_PER_AGENT_PAISE: int = 50_000_000  # Rs 5,00,000 (5 Lakhs)
    SLIPPAGE_BPS: int = 3
    STT_RATE: float = 0.001
    EXCHANGE_TURNOVER_RATE: float = 0.0000307
    SEBI_FEE_RATE: float = 0.000001
    STAMP_DUTY_RATE: float = 0.00015
    GST_RATE: float = 0.18
    DP_CHARGES_PAISE: int = 1500
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
    ORDER_VALIDITY_MODE: str = "NEXT_TRADING_DAY"
    MARKET_OPEN_TIME: str = "09:15"

    # --- Broker soft caps (§4.2; non-blocking, logged as CAP_BREACH) ---
    MAX_RISK_PCT_PER_TRADE: float = 2.0
    MAX_POSITION_PCT_OF_ACCOUNT: float = 20.0
    MAX_SECTOR_PCT_OF_ACCOUNT: float = 25.0

    # --- LLM providers (§3.2) ---
    EXECUTION_MODE: str = "backtest"
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    LLM_FALLBACK_PROVIDER: str = "groq"
    LLM_FALLBACK_MODEL: str = "openai/gpt-oss-120b"
    LLM_REASONING_EFFORT: str = "medium"
    LLM_MAX_OUTPUT_TOKENS: int = 4000
    LLM_TEMPERATURE: float = 0.2
    LLM_GEMINI_THINKING_BUDGET: int = 1536
    REFLECTION_GEMINI_THINKING_BUDGET: int = 3072

    # --- Reflection LLM providers ---
    REFLECTION_LLM_PROVIDER: str = "gemini"
    REFLECTION_LLM_MODEL: str = "gemini-3.8-flash"
    REFLECTION_LLM_FALLBACK_PROVIDER: str = "groq"
    REFLECTION_LLM_FALLBACK_MODEL: str = "openai/gpt-oss-120b"

    # --- Prompts (§3.2) ---
    MAX_CANDIDATES_PER_RUN: int = 10
    AGENT_RUN_DELAY_SEC: int = 60
    PROMPT_TOKEN_TARGET: int = 2800
    PROMPT_TOKEN_CEILING: int = 3800
    EPISODIC_MEMORY_LIMIT: int = 10
    MIN_CITED_METRICS: int = 3

    # --- Funnel (§6) ---
    MIN_SECTOR_COHORT: int = 8
    SECTOR_PERCENTILE_MIN: float = 0.0
    SECTOR_CAP_PER_AGENT: int = 2
    WATCHLIST_TARGET_SIZE_MIN: int = 8
    WATCHLIST_TARGET_SIZE_MAX: int = 10
    MIN_TURNOVER_RUPEES: int = 50_000_000

    # --- Learning (§5) ---
    MIN_CLOSED_TRADES_FOR_REFLECTION: int = 3
    FORWARD_HORIZONS: list[int] = Field(default_factory=lambda: [1, 5, 8, 10, 20, 60, 90, 120])
    HEURISTIC_ACTIVE_MIN_APPLICATIONS: int = 5
    HEURISTIC_ACTIVE_MIN_SUCCESS_RATE: float = 0.6
    HEURISTIC_REINFORCED_MIN_APPLICATIONS: int = 10
    HEURISTIC_REINFORCED_MIN_SUCCESS_RATE: float = 0.6
    HEURISTIC_WILSON_Z: float = 1.645
    HEURISTIC_ACTIVE_MIN_WILSON_SCORE: float = 0.50
    HEURISTIC_REINFORCED_MIN_WILSON_SCORE: float = 0.55
    HEURISTIC_DEPRECATED_MAX_SUCCESS_RATE: float = 0.4
    HEURISTIC_DEPRECATED_MIN_APPLICATIONS: int = 3
    HEURISTIC_DEPRECATED_STALE_DAYS: int = 30
    HEURISTIC_COMPLIANCE_MIN_APPLICATIONS: int = 5
    HEURISTIC_LOW_COMPLIANCE_THRESHOLD: float = 0.50
    HEURISTIC_HIGH_CONFIDENCE_THRESHOLD: float = 0.60
    MAX_ACTIVE_HEURISTICS_IN_PROMPT: int = 5
    REFLECTION_MAX_TOKENS: int = 8000
    MAX_NEW_HEURISTICS_PER_REFLECTION: int = 3
    HEURISTIC_ROLLING_WINDOW: int = 12
    HEURISTIC_ROLLING_DEMOTE_BELOW: float = 0.45
    HEURISTIC_SUCCESS_COST_HURDLE_PCT: float = 0.50

    # --- Forensics enrichment (§5.2 extended): secondary tags and post-exit facts ---
    LATE_ENTRY_LOOKBACK_SESSIONS: int = 10
    LATE_ENTRY_RUN_UP_PCT: float = 12.0
    GAP_DOWN_PCT: float = 3.0
    DEEP_DRAWDOWN_PCT: float = 8.0
    GAVE_BACK_MIN_MFE_PCT: float = 5.0
    GAVE_BACK_PCT: float = 4.0
    POST_EXIT_SHORT_DAYS: int = 5
    POST_EXIT_LONG_DAYS: int = 20
    EXITED_TOO_EARLY_PCT: float = 8.0
    GOOD_EXIT_PCT: float = 4.0

    # --- Data & corporate actions (§1.5, §2.5) ---
    CORP_ACTION_DIFF_PCT: float = 5.0
    CORP_ACTION_LOOKBACK_CANDLES: int = 10
    INGESTION_RETRY_COUNT: int = 3
    OHLCV_BACKFILL_DAYS: int = 400
    MARKET_QUOTE_BATCH_SIZE: int = 500
    VIX_BANDS: dict[str, float] = Field(default_factory=lambda: {"LOW_VOL": 14.0, "NORMAL": 18.0, "ELEVATED": 24.0})

    # --- Paths ---
    TIMEZONE: str = "Asia/Kolkata"
    PORTFOLIO_DB_PATH: str = "storage/ledger/portfolio.db"
    MARKET_DB_DIR: str = "storage/market"
    OHLCV_DB_PATH: str = "storage/market/ohlcv.db"
    INTRADAY_DB_PATH: str = "storage/market/intraday.db"
    MACRO_DB_PATH: str = "storage/market/macro.db"
    FUNDAMENTAL_DB_PATH: str = "storage/market/fundamental.db"
    NEWS_DB_PATH: str = "storage/market/news.db"
    BACKUP_DIR: str = "backups"
    FUNDAMENTAL_REFETCH_DAYS: int = 14
    DB_BUSY_TIMEOUT_MS: int = 5000
    UPSTOX_BASE_URL: str = "https://api.upstox.com"
    BACKTEST_DB_DIR: str = "storage/backtest"

    # --- API (Week 5 backend, Plan_v3 Part IV) ---
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )


settings = Settings()
