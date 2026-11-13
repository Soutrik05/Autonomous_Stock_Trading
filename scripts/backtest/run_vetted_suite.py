"""
Vetted Suite Backtest Runner across 3 Regimes:
1. Rolling Window 1 (rolling_w1: Bull Trend, 180 sessions)
2. Supplementary Window (supplementary_range: Range-Bound Compression, 51 sessions)
3. Rolling Window 2 (rolling_w2: High-Vol Correction & Recovery, 180 sessions)

Inherits vetted, regime-scoped, reinforced heuristics from:
storage/backtest/fleet_collective_memory.db

Models configured:
Trading Agent LLM: gemini-3.1-flash-lite
Reflection LLM:    gemini-3.8-flash
"""

import logging
import sys
import time
from pathlib import Path

# Ensure workspace root and src are in sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _ROOT / "src"
for p in (_SRC, _ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backtest.config import BACKTEST_WINDOWS
from backtest.engine import BacktestEngine
from backtest.reports import format_markdown_report, generate_window_report
from core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vetted_backtest_suite")


def run_window(window_id: str, db_path: Path, report_path: Path, memory_source: Path) -> dict:
    win = BACKTEST_WINDOWS[window_id]
    logger.info("=" * 80)
    logger.info("STARTING VETTED WALK-FORWARD WINDOW: [%s] — %s", win.window_id, win.name)
    logger.info("Historical Range: %s to %s (%d sessions)", win.start_date, win.end_date, win.sessions_count)
    logger.info("Regime:           %s (%s)", win.regime_label, win.description)
    logger.info("Trading Model:    %s (Provider: %s)", settings.LLM_MODEL, settings.LLM_PROVIDER)
    logger.info("Reflection Model: %s (Provider: %s)", settings.REFLECTION_LLM_MODEL, settings.REFLECTION_LLM_PROVIDER)
    logger.info("Inheriting From:  %s", memory_source)
    logger.info("Target DB:        %s", db_path)
    logger.info("Report Target:    %s", report_path)
    logger.info("=" * 80)

    def progress(day_idx: int, total: int, date_str: str) -> None:
        if day_idx % 10 == 0 or day_idx == 1 or day_idx == total:
            logger.info(
                "  -> [%s] Progress: %d/%d sessions (%.1f%%) | Date: %s",
                win.window_id,
                day_idx,
                total,
                (day_idx / total) * 100,
                date_str,
            )

    engine = BacktestEngine(
        window=win,
        db_path=db_path,
        fake_llm=False,
        use_cache=True,
        resume=True,
        progress_callback=progress,
        enable_heuristics=True,
        inherit_memory=memory_source,
    )

    t0 = time.time()
    res = engine.run()
    elapsed = time.time() - t0
    logger.info("Window [%s] execution finished in %.1fs (%.1f min).", win.window_id, elapsed, elapsed / 60)

    # Generate and save report
    try:
        rep = generate_window_report(db_path, res["window"])
        md_text = format_markdown_report(rep)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(md_text, encoding="utf-8")
        logger.info("Report saved to %s", report_path)
    except Exception as exc:
        logger.error("Failed to generate report for %s: %s", window_id, exc)

    return res


def main():
    start_total = time.time()
    logger.info("=" * 80)
    logger.info("STARTING VETTED MULTI-REGIME SUITE (OPTION 2)")
    logger.info("Trading Model:    %s", settings.LLM_MODEL)
    logger.info("Reflection Model: %s", settings.REFLECTION_LLM_MODEL)
    logger.info("=" * 80)

    memory_source = Path("storage/backtest/fleet_collective_memory.db").resolve()
    if not memory_source.exists():
        logger.error("Fleet collective memory not found at: %s", memory_source)
        sys.exit(1)

    windows = [
        (
            "rolling_w1",
            Path("storage/backtest/rolling_w1_vetted.db").resolve(),
            Path("storage/backtest/reports/rolling_w1_vetted.md").resolve(),
        ),
        (
            "supplementary_range",
            Path("storage/backtest/s1_vetted.db").resolve(),
            Path("storage/backtest/reports/s1_vetted.md").resolve(),
        ),
        (
            "rolling_w2",
            Path("storage/backtest/w2_vetted.db").resolve(),
            Path("storage/backtest/reports/w2_vetted.md").resolve(),
        ),
    ]

    results = []
    for win_id, db_path, report_path in windows:
        res = run_window(win_id, db_path, report_path, memory_source)
        results.append((win_id, res))

    total_elapsed = time.time() - start_total
    logger.info("=" * 80)
    logger.info("ALL 3 VETTED BACKTEST WINDOWS COMPLETED in %.1fs (%.1f min)", total_elapsed, total_elapsed / 60)
    for win_id, r in results:
        logger.info(" - Window %s: Status=%s", win_id, r.get("status", "SUCCESS"))
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

