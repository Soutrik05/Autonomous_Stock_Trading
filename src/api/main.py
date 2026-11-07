"""
FastAPI entry point mounting the leaderboard, portfolio, activity, health and backtest routes.
/memory and /baseline/comparison are phase 2 -- their route files are still docstring-only
stubs with no router object, so they are not imported here yet.
See Plan_v3 Part IV.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import activity, backtest, health, leaderboard, portfolio
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
app.include_router(backtest.router)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc.detail) if hasattr(exc, "detail") else "Not found."})
