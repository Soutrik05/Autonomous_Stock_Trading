"""
CLI entrypoint for StockMinds historical walk-forward backtests.
Supports running curated multi-regime windows or full rolling 180-day walk-forwards.
Usage:
  python -m backtest.runner --list-windows
  python -m backtest.runner --window rolling_w1 [--fake-llm]
  python -m backtest.runner --all-rolling [--fake-llm]
See Plan_v3 §System Overview.
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure src and workspace root are in sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _ROOT / "src"
for p in (_SRC, _ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dotenv import load_dotenv

load_dotenv()

from backtest.config import BACKTEST_WINDOWS, get_curated_regime_windows, get_rolling_windows
from backtest.engine import BacktestEngine
from backtest.reports import format_markdown_report, generate_window_report
from core.config import settings
from core.database import get_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("backtest.runner")


def main() -> None:
    parser = argparse.ArgumentParser(description="StockMinds Walk-Forward Backtest Runner.")
    parser.add_argument("--list-windows", action="store_true", help="List available rolling and regime windows")
    parser.add_argument("--window", type=str, default=None, help="Window ID to execute (e.g. rolling_w1)")
    parser.add_argument("--all-rolling", action="store_true", help="Run all rolling 180-day windows")
    parser.add_argument("--fake-llm", action="store_true", help="Use FakeLLM for rapid testing without API spend")
    parser.add_argument("--no-cache", action="store_true", help="Bypass LLM response cache")
    parser.add_argument("--resume", action="store_true", help="Resume from last completed session in database")
    parser.add_argument("--db-path", type=str, default=None, help="Custom isolated backtest database path")
    parser.add_argument(
        "--agents", nargs="+", default=None, help="Agent IDs to simulate (e.g. simons baseline-simons-rules)"
    )
    parser.add_argument("--output-report", type=str, default=None, help="Save markdown report to path")
    parser.add_argument(
        "--inherit-memory",
        type=str,
        default=None,
        help="Path to prior backtest DB to inherit active/reinforced heuristics from",
    )
    parser.add_argument(
        "--no-heuristics",
        "--disable-learning",
        dest="no_heuristics",
        action="store_true",
        help="Disable reflective learning heuristics",
    )
    args = parser.parse_args()

    ohlcv_conn = get_connection(settings.OHLCV_DB_PATH)
    try:
        rolling_windows = get_rolling_windows(ohlcv_conn)
        get_curated_regime_windows(ohlcv_conn)
    finally:
        ohlcv_conn.close()

    if args.list_windows:
        print("=" * 80)
        print("CURATED WALK-FORWARD REGIME WINDOWS (RECOMMENDED)")
        print("=" * 80)
        print(f"{'Window ID':<15} {'Regime':<18} {'Start Date':<12} {'End Date':<12} {'Sessions':<10} {'Description'}")
        print("-" * 80)
        for w in BACKTEST_WINDOWS.values():
            print(
                f"{w.window_id:<15} {w.regime_label:<18} {w.start_date:<12} {w.end_date:<12} {w.sessions_count:<10} {w.description}"
            )
        print("=" * 80)
        return

    # Determine windows to execute
    windows_to_run = []
    if args.all_rolling:
        windows_to_run = list(BACKTEST_WINDOWS.values())
    elif args.window:
        if args.window in BACKTEST_WINDOWS:
            windows_to_run = [BACKTEST_WINDOWS[args.window]]
        else:
            matching = [w for w in rolling_windows if w.window_id == args.window]
            if not matching:
                print(f"Error: Window '{args.window}' not found. Run with --list-windows to see valid options.")
                sys.exit(1)
            windows_to_run = matching
    else:
        # Default to first curated window (rolling_w1)
        windows_to_run = [BACKTEST_WINDOWS["rolling_w1"]]

    for win in windows_to_run:
        print("\n" + "=" * 80)
        print(f"RUNNING WALK-FORWARD WINDOW: [{win.window_id}] — {win.name}")
        print(f"Historical Range: {win.start_date} to {win.end_date} ({win.sessions_count} sessions)")
        print(f"Regime:           {win.regime_label} ({win.description})")
        print(f"LLM Engine:       {'FakeLLM (Offline Mode)' if args.fake_llm else settings.LLM_MODEL}")
        print(f"Agents Filter:    {', '.join(args.agents) if args.agents else 'All personas'}")
        print(f"Learning Module:  {'DISABLED (Ablation Mode)' if args.no_heuristics else 'ENABLED'}")
        if args.db_path:
            print(f"Custom DB:        {args.db_path}")
        print("=" * 80)

        def progress(day_idx: int, total: int, date_str: str) -> None:
            if day_idx % 10 == 0 or day_idx == total:
                print(
                    f"  -> Progress: {day_idx}/{total} sessions ({(day_idx / total) * 100:.1f}%) | Simulated Date: {date_str}"
                )

        engine = BacktestEngine(
            window=win,
            db_path=Path(args.db_path) if args.db_path else None,
            fake_llm=args.fake_llm,
            use_cache=not args.no_cache,
            resume=args.resume,
            progress_callback=progress,
            agent_ids=args.agents,
            enable_heuristics=not args.no_heuristics,
            inherit_memory=args.inherit_memory,
        )

        res = engine.run()
        print(f"\nWindow [{win.window_id}] completed in {res.get('elapsed_sec')}s.")

        # Generate Report
        rep = generate_window_report(Path(res["database_path"]), res["window"])
        md_text = format_markdown_report(rep)
        print("\n" + md_text)

        if args.output_report:
            out_p = Path(args.output_report).resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(md_text, encoding="utf-8")
            print(f"\nSaved report to: {out_p}")


if __name__ == "__main__":
    main()
