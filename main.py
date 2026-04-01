# =============================================================================
# main.py  —  single entry point
#
# RUN:  python main.py
#
# REQUIRED in .env:
#   GROQ_API_KEY       from console.groq.com  (free)
#   GROWW_API_KEY      from groww.in settings
#   GROWW_SECRET       from groww.in settings
# =============================================================================

import os
import sys
import time
import logging
from dotenv import load_dotenv

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger("main")

load_dotenv()


# ── 1. Fail fast on missing keys ──────────────────────────────────────────────

def check_env():
    missing = [k for k in ["GROQ_API_KEY", "GROWW_API_KEY", "GROWW_SECRET"]
               if not os.getenv(k)]
    if missing:
        print(f"\n❌  Missing environment variables: {', '.join(missing)}")
        print("    Copy .env.example → .env and fill in your keys.\n")
        sys.exit(1)


# ── 2. Smart RAG refresh (only when stale or missing) ─────────────────────────

def check_and_build_rag(db_path: str = "rag_db", max_age_hours: float = 24.0):
    index_path = os.path.join(db_path, "faiss.index")

    if not os.path.exists(index_path):
        print("📦  RAG database not found — building for the first time.")
        print("    This takes ~5-10 minutes. Future runs skip this step.\n")
        _rebuild_rag()
        return

    age_hours = (time.time() - os.path.getmtime(index_path)) / 3600
    if age_hours > max_age_hours:
        print(f"🔄  RAG is {age_hours:.1f} h old — refreshing...")
        _rebuild_rag()
    else:
        print(f"✅  RAG is fresh ({age_hours:.1f} h old) — skipping rebuild.")


def _rebuild_rag():
    # Import DIRECTLY — bypasses orchestrator/__init__.py
    # which would otherwise eagerly load graph.py → torch → crash
    import importlib.util, pathlib

    embedder_path = pathlib.Path(__file__).parent / "orchestrator" / "rag" / "embedder.py"
    spec          = importlib.util.spec_from_file_location("embedder", embedder_path)
    embedder_mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(embedder_mod)

    embedder_mod.Embedder().build_all()
    print("✅  RAG ready.\n")


# ── 3. Run ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    check_env()
    check_and_build_rag()

    # Import graph only AFTER RAG is built — torch must be working by this point
    from orchestrator.graph import run_trading_platform
    run_trading_platform()