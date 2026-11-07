"""
End-to-end walk-forward backtest baseline runner across all 3 windows:
1. Rolling Window 1 (Bull Trend: 2025-02-28 to 2025-11-21, 180 sessions)
2. Supplementary Window (Range-Bound Compression: 2025-11-24 to 2026-02-04, 51 sessions)
3. Rolling Window 2 (High Volatility Correction: 2026-02-05 to 2026-10-29, 180 sessions)

All personas running with heuristics active (Heuristics ON baseline).
Saves databases to:
- storage/backtest/rolling_w1_heuristics_on.db
- storage/backtest/supplementary_range_heuristics_on.db
- storage/backtest/rolling_w2_heuristics_on.db
"""

import logging
import sys
import time
from pathlib import Path

# Ensure workspace root and src are in sys.path
_ROOT = Path(__file__).resolve().parent.parent
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
logger = logging.getLogger("baseline_backtest_runner")


def run_window(window_id: str, db_path: Path, report_path: Path) -> dict:
    win = BACKTEST_WINDOWS[window_id]
    logger.info("=" * 80)
    logger.info("STARTING WALK-FORWARD WINDOW: [%s] — %s", win.window_id, win.name)
    logger.info("Historical Range: %s to %s (%d sessions)", win.start_date, win.end_date, win.sessions_count)
    logger.info("Regime:           %s (%s)", win.regime_label, win.description)
    logger.info("Active Model:     %s (Provider: %s)", settings.LLM_MODEL, settings.LLM_PROVIDER)
    logger.info("Isolated DB:      %s", db_path)
    logger.info("Report Target:    %s", report_path)
    logger.info("=" * 80)

    def progress(day_idx: int, total: int, date_str: str) -> None:
        if day_idx % 5 == 0 or day_idx == 1 or day_idx == total:
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
    logger.info("STARTING FULL BASELINE BACKTEST (HEURISTICS ON) ACROSS 3 WINDOWS")
    logger.info("LLM Provider: %s | Model: %s", settings.LLM_PROVIDER, settings.LLM_MODEL)
    logger.info("=" * 80)

    windows = [
        (
            "rolling_w1",
            Path("storage/backtest/rolling_w1_heuristics_on.db").resolve(),
            Path("reports/rolling_w1_heuristics_on_report.md").resolve(),
        ),
        (
            "supplementary_range",
            Path("storage/backtest/supplementary_range_heuristics_on.db").resolve(),
            Path("reports/supplementary_range_heuristics_on_report.md").resolve(),
        ),
        (
            "rolling_w2",
            Path("storage/backtest/rolling_w2_heuristics_on.db").resolve(),
            Path("reports/rolling_w2_heuristics_on_report.md").resolve(),
        ),
    ]

    for win_id, db_p, rep_p in windows:
        run_window(win_id, db_p, rep_p)

    total_elapsed = time.time() - start_total
    logger.info("=" * 80)
    logger.info("ALL 3 WALK-FORWARD WINDOWS COMPLETED in %.1fs (%.1f min)", total_elapsed, total_elapsed / 60)
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
