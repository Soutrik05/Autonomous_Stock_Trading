"""
API and evaluation tests against a temporary on-disk portfolio.db (the API opens it read-only).
"""
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evaluation.performance import max_drawdown_pct, sharpe_ratio
from settings import settings

_DB = Path(__file__).resolve().parents[2] / "db"


@pytest.fixture
def client(tmp_path, request):
    path = tmp_path / "portfolio.db"
    conn = sqlite3.connect(path)
    conn.executescript((_DB / "schema.sql").read_text(encoding="utf-8"))
    for m in sorted((_DB / "migrations").glob("*.sql")):
        if not m.name.startswith("0001_"):
            conn.executescript(m.read_text(encoding="utf-8"))
    now = "2026-01-01T00:00:00"
    for aid, kind in (("simons", "LLM"), ("baseline-simons-rules", "BASELINE")):
        conn.execute("INSERT INTO agents (id,name,philosophy,kind,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                     (aid, aid, "p", kind, now, now))
        for i, tot in enumerate([10_000_000, 10_100_000, 9_900_000, 10_300_000]):
            conn.execute("INSERT INTO daily_nav VALUES (?,?,?,?,?,?)",
                         (aid, f"2026-01-0{i + 1}", 0, tot, tot, 20000.0 + i * 100))
    conn.execute("INSERT INTO activity_log (agent_id,event_type,description,created_at) VALUES ('simons','BUY_FILLED','x','t')")
    conn.execute("INSERT INTO pipeline_runs (job,run_date,status,started_at) VALUES ('agents','2026-01-04','FAILED','t')")
    conn.commit()
    conn.close()
    olds = {k: getattr(settings, k) for k in ("PORTFOLIO_DB_PATH", "API_KEY")}
    object.__setattr__(settings, "PORTFOLIO_DB_PATH", str(path))
    object.__setattr__(settings, "API_KEY", "")
    request.addfinalizer(lambda: [object.__setattr__(settings, k, v) for k, v in olds.items()])
    from api.main import app
    return TestClient(app)


def test_metrics_math():
    assert max_drawdown_pct([100, 110, 99, 120]) == -10.0
    assert sharpe_ratio([100]) is None
    assert sharpe_ratio([100, 100, 100]) is None  # zero variance


def test_leaderboard_has_small_sample_notice(client):
    body = client.get("/api/leaderboard").json()
    a = next(x for x in body["agents"] if x["agent_id"] == "simons")
    assert a["small_sample"] and "Small sample" in a["small_sample_notice"]
    assert a["return_pct"] == 3.0 and a["max_drawdown_pct"] < 0


def test_agent_endpoints_and_404(client):
    for ep in ("positions", "orders", "decisions", "nav", "memory"):
        assert client.get(f"/api/agents/simons/{ep}").status_code == 200
    assert client.get("/api/agents/nobody/nav").status_code == 404
    assert len(client.get("/api/agents/simons/nav").json()["nav"]) == 4


def test_comparison_activity_health(client):
    assert len(client.get("/api/baseline/comparison").json()["curves"]) == 4
    assert client.get("/api/activity").json()["events"][0]["event_type"] == "BUY_FILLED"
    h = client.get("/api/health").json()
    assert h["status"] == "degraded" and h["failed_jobs"] == ["agents"]


def test_api_key_enforced_when_set_and_health_stays_public(client):
    object.__setattr__(settings, "API_KEY", "secret")
    assert client.get("/api/leaderboard").status_code == 401
    assert client.get("/api/leaderboard", headers={"X-API-Key": "secret"}).status_code == 200
    assert client.get("/api/health").status_code == 200


def test_api_is_read_only(client):
    assert client.post("/api/leaderboard").status_code == 405
