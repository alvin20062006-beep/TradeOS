from __future__ import annotations

import argparse
import html
import sys

from apps.desktop.runtime import TradeOSRuntime


def _error_html(message: str) -> str:
    safe_message = html.escape(message)
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>TradeOS Startup Error</title>
        <style>
          body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            font-family: "Segoe UI", sans-serif;
            background: #101820;
            color: #f7efe5;
          }}
          main {{
            width: min(720px, calc(100vw - 48px));
            padding: 32px;
            border: 1px solid rgba(255,255,255,.16);
            border-radius: 24px;
            background: rgba(255,255,255,.06);
            box-shadow: 0 30px 80px rgba(0,0,0,.35);
          }}
          code {{
            display: block;
            margin-top: 16px;
            padding: 16px;
            white-space: pre-wrap;
            border-radius: 14px;
            background: rgba(0,0,0,.35);
            color: #ffd0c2;
          }}
        </style>
      </head>
      <body>
        <main>
          <p>TradeOS desktop shell could not start the local backend.</p>
          <p>TradeOS 桌面壳无法启动本地后端。</p>
          <code>{safe_message}</code>
        </main>
      </body>
    </html>
    """


def run_desktop() -> int:
    try:
        import webview
    except Exception as exc:
        print("pywebview is required for the desktop shell. Install requirements-local.txt.", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    runtime = TradeOSRuntime()
    try:
        state = runtime.start()
        window = webview.create_window(
            "TradeOS",
            state.console_url,
            width=1360,
            height=900,
            min_size=(1100, 720),
            text_select=True,
        )
        window.events.closed += runtime.stop
        webview.start(debug=False)
        return 0
    except Exception as exc:
        runtime.stop()
        window = webview.create_window(
            "TradeOS Startup Error",
            html=_error_html(str(exc)),
            width=900,
            height=620,
            text_select=True,
        )
        window.events.closed += runtime.stop
        webview.start(debug=False)
        return 1


def run_smoke() -> int:
    runtime = TradeOSRuntime()
    state = runtime.start(timeout_seconds=30)
    try:
        health = runtime.health()
        print(f"desktop_runtime_ok base_url={state.base_url} console={state.console_url} health={health}")
    finally:
        runtime.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TradeOS desktop shell")
    parser.add_argument("--smoke", action="store_true", help="Start and stop the embedded backend without opening a GUI")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.smoke:
        return run_smoke()
    return run_desktop()


if __name__ == "__main__":
    raise SystemExit(main())

