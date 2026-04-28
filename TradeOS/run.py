"""Unified local launcher for TradeOS desktop, API, and CLI checks."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parent.resolve()
PYTHON = sys.executable
API_URL = "http://127.0.0.1:8000"
CONSOLE_URL = f"{API_URL}/console/"


def run_api() -> int:
    return subprocess.call(
        [
            PYTHON,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=ROOT,
    )


def run_console() -> int:
    return subprocess.call(
        [PYTHON, "-m", "apps.run_console"],
        cwd=ROOT,
    )


def run_desktop() -> int:
    return subprocess.call(
        [PYTHON, "-m", "apps.desktop.main"],
        cwd=ROOT,
    )


def run_desktop_smoke() -> int:
    return subprocess.call(
        [PYTHON, "-m", "apps.desktop.main", "--smoke"],
        cwd=ROOT,
    )


def run_status() -> int:
    return subprocess.call(
        [PYTHON, "-m", "apps.cli", "status"],
        cwd=ROOT,
    )


def run_pipeline_live(symbol: str, timeframe: str, lookback: int, news_limit: int) -> int:
    return subprocess.call(
        [
            PYTHON,
            "-m",
            "apps.cli",
            "pipeline",
            "run-live",
            "--symbol",
            symbol,
            "--timeframe",
            timeframe,
            "--lookback",
            str(lookback),
            "--news-limit",
            str(news_limit),
        ],
        cwd=ROOT,
    )


def run_start() -> int:
    return run_desktop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TradeOS unified local launcher")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Start the TradeOS desktop shell")
    sub.add_parser("desktop", help="Start the TradeOS desktop shell")
    sub.add_parser("desktop-smoke", help="Start and stop the embedded backend without opening a GUI")
    sub.add_parser("api", help="Start API only")
    sub.add_parser("console", help="Developer fallback: start API and open /console/ in the browser")
    sub.add_parser("status", help="Check local API status via CLI")

    live = sub.add_parser("pipeline-live", help="Run real-data live pipeline via CLI")
    live.add_argument("--symbol", required=True)
    live.add_argument("--timeframe", default="1d")
    live.add_argument("--lookback", type=int, default=180)
    live.add_argument("--news-limit", type=int, default=10)

    parser.set_defaults(command="start")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "api":
        return run_api()
    if args.command == "desktop":
        return run_desktop()
    if args.command == "desktop-smoke":
        return run_desktop_smoke()
    if args.command == "console":
        return run_console()
    if args.command == "status":
        return run_status()
    if args.command == "pipeline-live":
        return run_pipeline_live(
            symbol=args.symbol,
            timeframe=args.timeframe,
            lookback=args.lookback,
            news_limit=args.news_limit,
        )
    return run_start()


if __name__ == "__main__":
    raise SystemExit(main())
