"""Global system configuration for Autonomous Stock Trading System.

Uses Pydantic v2 BaseSettings for type-safe environment variable parsing,
validation, and default settings.
"""

from typing import Any

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database paths ---
    MARKET_DB_PATH: str = "storage/market/market.db"
    LEDGER_DB_PATH: str = "storage/ledger/ledger.db"
    AGENT_MEMORY_DB_PATH: str = "storage/ledger/ledger.db"

    # --- Capital & Cash (§4.1) ---
    INITIAL_CAPITAL_PER_AGENT_RUPEES: int = 1_000_000
    MAX_CONCENTRATION_PCT: float = 0.20
    MAX_CASH_PCT: float = 0.90
    MIN_CASH_BUFFER_PCT: float = 0.05
    CIRCUIT_LIMIT_BUFFER_PCT: float = 0.02
    CIRCUIT_COOLDOWN_DAYS: int = 5

    # --- Execution & Costs (§4.3) ---
    SLIPPAGE_BPS_LARGE_CAP: int = 5
    SLIPPAGE_BPS_MID_CAP: int = 10
    SLIPPAGE_BPS_SMALL_CAP: int = 15
    STT_EQUITY_DELIVERY_PCT: float = 0.001
    EXCHANGE_TXN_CHARGE_NSE_PCT: float = 0.0000325
    SEBI_TURNOVER_CHARGE_PCT: float = 0.000001
    STAMP_DUTY_BUY_DELIVERY_PCT: float = 0.00015
    GST_RATE: float = 0.18
    BROKERAGE_EQUITY_DELIVERY_PCT: float = 0.0

    # --- Holding periods ---
    MIN_HOLDING_DAYS_SWING: int = 5
    MAX_HOLDING_DAYS_SWING: int = 20
    MIN_HOLDING_DAYS_MOMENTUM: int = 1
    MAX_HOLDING_DAYS_MOMENTUM: int = 5
    MAX_HOLDING_DAYS_LONG_TERM: int = 90
    DEFAULT_MAX_HOLDING_DAYS: int = 30

    # --- Universe & Data (§2.1) ---
    LOOKBACK_YEARS: int = 5
    INTRADAY_LOOKBACK_DAYS: int = 365
    INDIA_VIX_HIGH_THRESHOLD: float = 24.0
    INDIA_VIX_LOW_THRESHOLD: float = 13.0
    INDEX_MA_WINDOW: int = 50

    # --- Upstox API credentials (§2.2) ---
    UPSTOX_API_KEY: str = ""
    UPSTOX_API_SECRET: str = ""
    UPSTOX_REDIRECT_URI: str = "http://localhost:8000/callback"
    UPSTOX_ACCESS_TOKEN: str = ""
    UPSTOX_TOKEN_EXPIRY: str = ""

    # --- LLM providers (§3.2) ---
    EXECUTION_MODE: str = "backtest"
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    LLM_FALLBACK_PROVIDER: str = "groq"
    LLM_FALLBACK_MODEL: str = "openai/gpt-oss-120b"
    LLM_REASONING_EFFORT: str = "medium"
    LLM_TEMPERATURE: float = 0.2
    LLM_REQUEST_TIMEOUT_SECONDS: int = 30
    LLM_RETRY_ATTEMPTS: int = 3
    LLM_RETRY_BASE_WAIT_SECONDS: float = 1.0

    # --- Reflection LLM providers ---
    REFLECTION_LLM_PROVIDER: str = "gemini"
    REFLECTION_LLM_MODEL: str = "gemini-3.8-flash"
    REFLECTION_LLM_FALLBACK_PROVIDER: str = "groq"
    REFLECTION_LLM_FALLBACK_MODEL: str = "openai/gpt-oss-120b"

    # --- Watchlist (§2.3) ---
    WATCHLIST_MAX_PER_CANDIDATE: int = 3
    WATCHLIST_TARGET_SIZE_MIN: int = 5
    WATCHLIST_TARGET_SIZE_MAX: int = 10
    MIN_TURNOVER_RUPEES: int = 50_000_000

    # --- Persona Parameters (§3.1) - Single Source of Truth ---
    PERSONAS: dict[str, dict[str, Any]] = Field(
        default_factory=lambda: {
            "jhunjhunwala": {
                "name": "Rakesh Jhunjhunwala",
                "style": "High-conviction value compounder",
                "holding_days_min": 10,
                "holding_days_max": 90,
                "min_pe": 0.0,
                "max_pe": 35.0,
                "min_roce_pct": 15.0,
                "min_roe_pct": 15.0,
                "max_debt_to_equity": 1.0,
                "min_cfo_to_pat": 0.8,
                "preferred_sector": None,
                "max_concentration_pct": 0.25,
                "regime_preferences": {
                    "BULL_TREND": 1.0,
                    "BEAR_TREND": 0.5,
                    "RANGE_BOUND": 0.7,
                    "HIGH_VOLATILITY": 0.5,
                },
            },
            "lynch": {
                "name": "Peter Lynch",
                "style": "Growth At Reasonable Price (GARP)",
                "holding_days_min": 5,
                "holding_days_max": 60,
                "max_peg": 1.2,
                "min_pat_growth_pct": 15.0,
                "max_debt_to_equity": 0.8,
                "min_roe_pct": 12.0,
                "preferred_sector": None,
                "max_concentration_pct": 0.20,
                "regime_preferences": {
                    "BULL_TREND": 1.0,
                    "BEAR_TREND": 0.6,
                    "RANGE_BOUND": 0.8,
                    "HIGH_VOLATILITY": 0.6,
                },
            },
            "marks": {
                "name": "Howard Marks",
                "style": "Contrarian value and risk-aware cycle investor",
                "holding_days_min": 10,
                "holding_days_max": 90,
                "max_pe_percentile": 30.0,
                "min_cfo_to_pat": 1.0,
                "max_debt_to_equity": 0.5,
                "min_fcf_yield_pct": 4.0,
                "preferred_sector": None,
                "max_concentration_pct": 0.20,
                "regime_preferences": {
                    "BULL_TREND": 0.6,
                    "BEAR_TREND": 1.0,
                    "RANGE_BOUND": 0.9,
                    "HIGH_VOLATILITY": 0.8,
                },
            },
            "simons": {
                "name": "Jim Simons",
                "style": "Pure quantitative momentum and statistical anomaly",
                "holding_days_min": 1,
                "holding_days_max": 10,
                "min_rsi_14": 55.0,
                "max_rsi_14": 80.0,
                "min_zscore_close_20": 0.5,
                "min_volume_surge_ratio": 1.5,
                "max_concentration_pct": 0.15,
                "regime_preferences": {
                    "BULL_TREND": 1.0,
                    "BEAR_TREND": 0.3,
                    "RANGE_BOUND": 0.4,
                    "HIGH_VOLATILITY": 0.5,
                },
            },
            "varsity": {
                "name": "Zerodha Varsity",
                "style": "Disciplined dual-confluence technical swing trader",
                "holding_days_min": 3,
                "holding_days_max": 20,
                "min_rsi_14": 40.0,
                "max_rsi_14": 65.0,
                "require_ema_crossover": True,
                "max_concentration_pct": 0.20,
                "regime_preferences": {
                    "BULL_TREND": 0.9,
                    "BEAR_TREND": 0.4,
                    "RANGE_BOUND": 0.8,
                    "HIGH_VOLATILITY": 0.5,
                },
            },
        }
    )

    # --- Learning (§5) ---
    MIN_CLOSED_TRADES_FOR_REFLECTION: int = 3
    FORWARD_HORIZONS: list[int] = Field(default_factory=lambda: [1, 5, 8, 10, 20, 60, 90, 120])
    MIN_FORENSIC_GAP_PCT: float = 3.0
    MAX_ACTIVE_HEURISTICS_IN_PROMPT: int = 5
    MAX_PENDING_PROMOTIONS: int = 3
    MAX_HEURISTICS_PER_REFLECTION: int = 3
    MIN_EVAL_PERIOD_DAYS: int = 14
    MAX_UNREINFORCED_DAYS: int = 30
    PROMOTION_CONFIDENCE_THRESHOLD: float = 0.70
    REINFORCEMENT_BOOST: float = 0.05
    CONTRADICTION_PENALTY: float = 0.10
    DEMOTION_THRESHOLD: float = 0.30
    MAX_ACTIVE_HEURISTICS_PER_AGENT: int = 10
    BENCHMARK_PROXIES: dict[str, str] = Field(
        default_factory=lambda: {
            "NIFTY_50": "^NSEI",
            "NIFTY_MIDCAP_100": "^CRSLDX",
            "NIFTY_SMALLCAP_100": "^CNXSC",
        }
    )

    # --- Evaluation (§6) ---
    TRADING_DAYS_PER_YEAR: int = 252
    RISK_FREE_RATE_ANNUAL: float = 0.065
    EVAL_TOP_N_SECTORS: int = 5

    # --- Alerting & Telegram (§7.2) ---
    ENABLE_ALERTS: bool = False
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_RATE_LIMIT_PER_MINUTE: int = 30

    # --- System & Operational (§8.3) ---
    LOG_LEVEL: str = "INFO"
    PROMETHEUS_METRICS_PORT: int = 8001
    MAX_WORKERS: int = 4
    PRICE_CACHE_EXPIRY_MINUTES: int = 15
    FUNDAMENTAL_REFETCH_DAYS: int = 14
    DB_BUSY_TIMEOUT_MS: int = 5000
    UPSTOX_BASE_URL: str = "https://api.upstox.com"
    BACKTEST_DB_DIR: str = "storage/backtest"

    # --- API (Week 5 backend, Plan_v3 Part IV) ---
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )


settings = Settings()
