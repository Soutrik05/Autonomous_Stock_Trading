"""
FastAPI entry point mounting the leaderboard, portfolio, activity, baseline, memory and health routes.
Read-only: opens portfolio.db in query-only mode; the scheduler process is the only writer.
See Plan_v3 Part IV.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import activity, baseline, health, leaderboard, memory, portfolio
from settings import settings

app = FastAPI(
    title="StockMinds API",
    description="Read-only API for a paper-trading research system. Educational only, not investment advice.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.API_CORS_ORIGINS.split(",") if o.strip()],
    allow_methods=["GET"],
    allow_headers=["X-API-Key"],
)
for module in (leaderboard, portfolio, memory, baseline, activity, health):
    app.include_router(module.router)


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Liveness probe with no database access."""
    return {"ok": True}
