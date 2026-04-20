"""Unified local launcher for API, web console, and CLI checks."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser
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
    api_proc = subprocess.Popen(
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
    try:
        time.sleep(4)
        webbrowser.open(CONSOLE_URL, new=2, autoraise=True)
        return api_proc.wait()
    except KeyboardInterrupt:
        api_proc.terminate()
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TradeOS unified local launcher")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Start API and open the FastAPI web console")
    sub.add_parser("api", help="Start API only")
    sub.add_parser("console", help="Start console only")
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
