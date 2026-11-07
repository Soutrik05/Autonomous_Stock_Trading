"""
FastAPI entry point mounting every phase-1 and phase-2 route.
See Plan_v3 Part IV.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import activity, backtest, baseline, funnel, health, leaderboard, memory, portfolio
from core.config import settings

app = FastAPI(
    title="StockMinds REST API",
    description="Read-only telemetry and evaluation endpoints for StockMinds multi-agent paper trading.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],  # API is strictly read-only
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(activity.router)
app.include_router(leaderboard.router)
app.include_router(portfolio.router)
app.include_router(memory.router)
app.include_router(baseline.router)
app.include_router(funnel.router)
app.include_router(backtest.router)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc.detail) if hasattr(exc, "detail") else "Not found."})
