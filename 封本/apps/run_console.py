# -*- coding: utf-8 -*-
"""
apps/run_console.py — Zero-Hue AI Trading Console launcher

Design Reference: awesome-design-md/design-md/ai-trading/DESIGN.md
Usage:
    python -m apps.run_console          # dev (auto port)
    python -m apps.run_console --prod  # production mode
    python -m apps.run_console --port 9000  # explicit port
"""
from __future__ import annotations

import argparse
import os
import sys
import subprocess
import time
import socket
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8501
FALLBACK_PORTS = [8502, 8503, 8510, 8511, 8512]
DEFAULT_HOST = "localhost"


def _find_free_port(start_port: int, fallback_ports: list[int]) -> int:
    """Find first available port starting from start_port."""
    for port in [start_port] + fallback_ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"All ports ({start_port}, {fallback_ports}) are in use")


def _open_browser(url: str) -> None:
    """Open URL in default browser, ignoring errors."""
    try:
        webbrowser.open(url, new=2, autoraise=True)
    except Exception:
        pass


def _wait_for_streamlit_ready(url: str, timeout: float = 10.0) -> bool:
    """Poll Streamlit health endpoint until ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            import requests
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _check_api_running() -> bool:
    """Check if API is already running at localhost:8000."""
    try:
        import requests
        r = requests.get("http://127.0.0.1:8000/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _start_api_if_needed() -> bool:
    """Start API in background if not already running. Returns True if already/now running."""
    if _check_api_running():
        print("  [OK] API already running at http://127.0.0.1:8000")
        return True

    api_cmd = [
        sys.executable, "-m", "uvicorn",
        "apps.api.main:app",
        "--host", "127.0.0.1",
        "--port", "8000",
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
    except Exception as e:
        print(f"  [WARN] Could not start API: {e}")
        return False

    # Wait for API to be ready
    print("  Waiting for API to start...")
    for _ in range(15):
        time.sleep(1)
        if _check_api_running():
            print("  [OK] API started at http://127.0.0.1:8000")
            return True
    print("  [WARN] API did not respond in 15s")
    return False


def _build_args(console_path: str, port: int, prod: bool) -> list[str]:
    # Use minimal args — config.toml handles headless/email/gatherUsageStats
    args = [
        sys.executable, "-m", "streamlit", "run",
        console_path,
        "--server.port", str(port),
    ]
    return args


def _streamlit_env() -> dict:
    """Return env dict so Streamlit finds the config.toml in apps/console/.streamlit/."""
    cfg_dir = str(Path(__file__).parent.resolve() / ".streamlit")
    return {"STREAMLIT_CONFIG_DIR": cfg_dir}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Trading Console — Zero-Hue Design System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "\nExamples:\n"
            "  python -m apps.run_console\n"
            "  python -m apps.run_console --prod\n"
            "  python -m apps.run_console --port 9000\n"
        ),
    )
    parser.add_argument(
        "--port", "-p", type=int, default=None,
        help=f"Port to serve on (default: auto-detect from {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--prod", action="store_true",
        help="Production mode",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check dependencies and exit",
    )
    args = parser.parse_args()

    if args.check:
        _check_deps()
        return

    # Find port
    if args.port:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", args.port))
            port = args.port
        except OSError:
            print(f"[WARN] Port {args.port} is in use. Switching to auto-detect.")
            port = _find_free_port(DEFAULT_PORT, FALLBACK_PORTS)
    else:
        port = _find_free_port(DEFAULT_PORT, FALLBACK_PORTS)

    console_path = str(Path(__file__).parent.resolve() / "console" / "main.py")
    host = DEFAULT_HOST
    url = f"http://{host}:{port}"

    # Ensure API is running
    api_ok = _start_api_if_needed()

    print(f"\n{'='*50}")
    print(f"  AI Trading Console")
    print(f"  Design: Zero-Hue (ai-trading DESIGN.md)")
    print(f"  Console URL:  {url}")
    if api_ok:
        print(f"  API URL:      http://127.0.0.1:8000")
    print(f"{'='*50}\n")

    cmd = _build_args(console_path, port, args.prod)

    try:
        # Open browser BEFORE waiting for streamlit (Streamlit opens browser itself)
        print(f"  Opening browser...")
        _open_browser(url)
        print(f"  Browser launched.\n")

        # Run streamlit with env pointing to config.toml
        env = {**os.environ, **_streamlit_env()}
        subprocess.run(cmd, check=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"\n[Error] Streamlit exited with code {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\n[Console] Stopped.")


def _check_deps() -> None:
    print("Checking dependencies...")
    try:
        import streamlit
        print(f"  [OK] streamlit {streamlit.__version__}")
    except ImportError:
        print("  [MISSING] streamlit — pip install streamlit")
    try:
        import requests
        print(f"  [OK] requests {requests.__version__}")
    except ImportError:
        print("  [MISSING] requests — pip install requests")
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
    print("  All core deps OK")


if __name__ == "__main__":
    main()
