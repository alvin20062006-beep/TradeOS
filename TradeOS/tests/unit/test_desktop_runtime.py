from __future__ import annotations

from apps.desktop.runtime import TradeOSRuntime


def test_desktop_runtime_starts_and_stops_embedded_backend() -> None:
    runtime = TradeOSRuntime()
    state = runtime.start(timeout_seconds=30)
    try:
        health = runtime.health()
        assert state.console_url.endswith("/console/")
        assert health.get("status") == "ok"
    finally:
        runtime.stop()
