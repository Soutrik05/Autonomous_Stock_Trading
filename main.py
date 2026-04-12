# =============================================================================
# main.py  —  single entry point
#
# REQUIRED in .env:
#   GROQ_API_KEY       from console.groq.com
#   GROWW_API_KEY      from groww.in
#   GROWW_SECRET       from groww.in
# =============================================================================

import os
import sys
import logging
from dotenv import load_dotenv
from orchestrator.graph import run_trading_platform

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger("main")


# ── 1. Fail fast on missing keys ──────────────────────────────────────────────
def check_env():
    
    load_dotenv()
    missing = [k for k in ["GROQ_API_KEY", "GROWW_API_KEY", "GROWW_SECRET"]
               if not os.getenv(k)]
    if missing:
        print(f"\n❌  Missing environment variables: {', '.join(missing)}")
        sys.exit(1)


# ── 2. Check if RAG is present (only when missing) ─────────────────────────
def check_and_build_rag(db_path: str = "rag_db", max_age_hours: float = 24.0):
    index_path = os.path.join(db_path, "faiss.index")

    if not os.path.exists(index_path):
        print("  RAG database not found — building for the first time. (ET: 5-10 minutes) \n")
        _rebuild_rag()
        return


def _rebuild_rag():
    import importlib.util, pathlib
    embedder_path = pathlib.Path(__file__).parent / "orchestrator" / "rag" / "embedder.py"
    spec          = importlib.util.spec_from_file_location("embedder", embedder_path)
    embedder_mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(embedder_mod)

    embedder_mod.Embedder().build_all()
    print("  RAG ready.\n")


# ── 3. Run ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    check_env()
    check_and_build_rag()
   
    run_trading_platform()