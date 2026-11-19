"""
Persistent SQLite-backed cache for LLM inference decisions in backtesting.
Prevents duplicate API calls across repeated backtests, parameter sweeps,
and overlapping rolling windows.
Provides CachedLLMClient wrapping LLMClient.
See Plan_v3 §3.2, §5.6.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from llm.client import LLMClient, LLMResult

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DB_PATH = Path("storage/backtest/llm_cache.db")


class LLMResponseCache:
    def __init__(self, db_path: Path | None = None):
        self.db_path = (db_path or DEFAULT_CACHE_DB_PATH).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
            self._conn.execute("PRAGMA busy_timeout = 30000")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __del__(self) -> None:
        self.close()

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key      TEXT PRIMARY KEY,
                agent_id       TEXT NOT NULL,
                run_date       TEXT NOT NULL,
                model          TEXT NOT NULL,
                prompt_hash    TEXT NOT NULL,
                raw_response   TEXT NOT NULL,
                decisions_json TEXT NOT NULL,
                tokens_in      INTEGER DEFAULT 0,
                tokens_out     INTEGER DEFAULT 0,
                latency_ms     INTEGER DEFAULT 0,
                created_at     TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_llm_cache_agent_date ON llm_cache(agent_id, run_date)")
        conn.commit()

    @staticmethod
    def compute_cache_key(
        agent_id: str,
        run_date: str,
        candidate_or_prompt: Any,
        model: str,
        extra_salt: str = "v1",
    ) -> str:
        """Deterministically hashes agent ID, date, candidates/prompt, and model."""
        if isinstance(candidate_or_prompt, (list, tuple, set)):
            content_str = ",".join(sorted(str(x) for x in candidate_or_prompt))
        else:
            content_str = str(candidate_or_prompt)
        raw = f"{agent_id}|{run_date}|{content_str}|{model}|{extra_salt}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self,
        agent_id: str,
        run_date: str,
        candidate_or_prompt: Any,
        model: str,
    ) -> dict[str, Any] | None:
        """Returns cached entry if present, else None."""
        key = self.compute_cache_key(agent_id, run_date, candidate_or_prompt, model)
        conn = self._get_conn()
        row = conn.execute(
            "SELECT raw_response, decisions_json, tokens_in, tokens_out, latency_ms, created_at FROM llm_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row:
            return {
                "cache_key": key,
                "raw_response": row["raw_response"],
                "decisions": json.loads(row["decisions_json"]) if row["decisions_json"] else [],
                "tokens_in": row["tokens_in"],
                "tokens_out": row["tokens_out"],
                "latency_ms": row["latency_ms"],
                "created_at": row["created_at"],
            }
        return None

    def set(
        self,
        agent_id: str,
        run_date: str,
        candidate_or_prompt: Any,
        model: str,
        raw_response: str,
        decisions: list[dict[str, Any]] | None = None,
        created_at_iso: str | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: int = 0,
    ) -> str:
        """Stores decision payload in cache."""
        key = self.compute_cache_key(agent_id, run_date, candidate_or_prompt, model)
        conn = self._get_conn()
        now_iso = created_at_iso or datetime.now().isoformat()
        prompt_str = candidate_or_prompt if isinstance(candidate_or_prompt, str) else json.dumps(candidate_or_prompt)
        dec_json = json.dumps(decisions) if decisions is not None else "[]"
        conn.execute(
            """
            INSERT OR REPLACE INTO llm_cache (
                cache_key, agent_id, run_date, model, prompt_hash, raw_response,
                decisions_json, tokens_in, tokens_out, latency_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                agent_id,
                run_date,
                model,
                prompt_str[:128],
                raw_response,
                dec_json,
                tokens_in,
                tokens_out,
                latency_ms,
                now_iso,
            ),
        )
        conn.commit()
        return key


class CachedLLMClient(LLMClient):
    """
    Wraps an underlying LLMClient and intercepts complete() calls with SQLite caching.
    Contextualized with current agent_id and run_date.
    """

    def __init__(
        self,
        inner_client: LLMClient,
        cache: LLMResponseCache | None = None,
        agent_id: str = "simons",
        run_date: str = "2026-01-01",
        model: str = "cached-model",
    ):
        self.inner_client = inner_client
        self.cache = cache or LLMResponseCache()
        self.agent_id = agent_id
        self.run_date = run_date
        self.model = getattr(inner_client, "_model_name", getattr(inner_client, "_model", model))

    def set_context(self, agent_id: str, run_date: str) -> None:
        self.agent_id = agent_id
        self.run_date = run_date

    def complete(
        self,
        system: str,
        user: str,
        reasoning_effort: str | None = None,
        max_output_tokens: int | None = None,
        response_schema: dict | None = None,
    ) -> LLMResult:
        prompt_content = f"{system}\n---\n{user}"
        p_hash = hashlib.sha256(prompt_content.encode("utf-8")).hexdigest()

        cached = self.cache.get(self.agent_id, self.run_date, p_hash, self.model)
        if cached is not None:
            logger.info("LLM cache hit for agent=%s date=%s", self.agent_id, self.run_date)
            return LLMResult(
                text=cached["raw_response"],
                tokens_in=cached.get("tokens_in", 0),
                tokens_out=cached.get("tokens_out", 0),
                latency_ms=cached.get("latency_ms", 0),
                model=self.model,
                finish_reason="stop",
            )

        result = self.inner_client.complete(
            system,
            user,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            response_schema=response_schema,
        )

        self.cache.set(
            agent_id=self.agent_id,
            run_date=self.run_date,
            candidate_or_prompt=p_hash,
            model=self.model,
            raw_response=result.text,
            decisions=[],
            created_at_iso=datetime.now().isoformat(),
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            latency_ms=result.latency_ms,
        )
        return result
