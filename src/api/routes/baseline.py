"""
GET /api/baseline/comparison: LLM Simons vs rules Simons vs Nifty 500 plus forward-return deltas.
See Plan_v3 Part IV.
"""
import sqlite3

from fastapi import APIRouter, Depends

from api.deps import AuthDep, get_db
from evaluation.comparison import build_comparison

router = APIRouter(prefix="/api/baseline", tags=["baseline"], dependencies=[AuthDep])


@router.get("/comparison")
def comparison(conn: sqlite3.Connection = Depends(get_db)):
    return build_comparison(conn)
