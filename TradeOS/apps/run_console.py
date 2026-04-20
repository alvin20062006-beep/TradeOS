# -*- coding: utf-8 -*-
"""
apps/run_console.py - TradeOS web console launcher.

The default console surface is now the FastAPI-served web console at /console/.
Legacy Streamlit remains available under apps/console/ as a fallback, but it is
no longer the default entry point.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

API_HOST = "127.0.0.1"
API_PORT = 8000
API_BASE = f"http://{API_HOST}:{API_PORT}"
CONSOLE_URL = f"{API_BASE}/console/"


def _open_browser(url: str) -> None:
    try:
        webbrowser.open(url, new=2, autoraise=True)
    except Exception:
        pass


def _wait_for_api_ready(url: str = f"{API_BASE}/health", timeout: float = 20.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass
        time.sleep(0.5)
    return False


def _check_api_running() -> bool:
    try:
        with urllib.request.urlopen(f"{API_BASE}/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _start_api_if_needed() -> bool:
    if _check_api_running():
        print(f"  [OK] API already running at {API_BASE}")
        return True

    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "apps.api.main:app",
        "--host",
        API_HOST,
        "--port",
        str(API_PORT),
    ]

    print("  Starting API server in background...")
    try:
        subprocess.Popen(
            api_cmd,
            cwd=str(Path(__file__).parent.parent.resolve()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except Exception as exc:
        print(f"  [WARN] Could not start API: {exc}")
        return False

    print("  Waiting for API to start...")
    if _wait_for_api_ready():
        print(f"  [OK] API started at {API_BASE}")
        return True
    print("  [WARN] API did not respond in time")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TradeOS web console launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "\nExamples:\n"
            "  python -m apps.run_console\n"
            "  python -m apps.run_console --check\n"
            "  python -m apps.run_console --no-browser\n"
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check dependencies and exit",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open the browser after the API is ready.",
    )
    args = parser.parse_args()

    if args.check:
        _check_deps()
        return

    api_ok = _start_api_if_needed()

    print(f"\n{'=' * 50}")
    print("  TradeOS Web Console")
    print(f"  Console URL:  {CONSOLE_URL}")
    if api_ok:
        print(f"  API URL:      {API_BASE}")
    print(f"{'=' * 50}\n")

    if not api_ok:
        sys.exit(1)

    if not args.no_browser:
        print("  Opening browser...")
        _open_browser(CONSOLE_URL)
        print("  Browser launched.\n")

    print("  Web console is served directly by FastAPI.")
    print("  Legacy Streamlit stays in apps/console/ as a fallback only.")


def _check_deps() -> None:
    print("Checking dependencies...")
    try:
        import fastapi

        print(f"  [OK] fastapi {fastapi.__version__}")
    except ImportError:
        print("  [MISSING] fastapi")
    try:
        import uvicorn

        print(f"  [OK] uvicorn {uvicorn.__version__}")
    except ImportError:
        print("  [MISSING] uvicorn")
    print("  [OK] urllib standard library")
    print("  Legacy Streamlit is not required for the default launcher.")


if __name__ == "__main__":
    main()
