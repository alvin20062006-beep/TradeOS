from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests
import uvicorn


@dataclass(slots=True)
class RuntimeState:
    host: str
    port: int
    base_url: str
    console_url: str


class TradeOSRuntime:
    """Owns the embedded FastAPI server used by the desktop shell."""

    def __init__(self, host: str = "127.0.0.1", port: Optional[int] = None) -> None:
        self.host = host
        self.port = port or self._find_free_port()
        self.state = RuntimeState(
            host=self.host,
            port=self.port,
            base_url=f"http://{self.host}:{self.port}",
            console_url=f"http://{self.host}:{self.port}/console/",
        )
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, timeout_seconds: float = 30.0) -> RuntimeState:
        if self._thread and self._thread.is_alive():
            return self.state

        config = uvicorn.Config(
            "apps.api.main:app",
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="tradeos-fastapi", daemon=True)
        self._thread.start()
        self._wait_until_ready(timeout_seconds)
        return self.state

    def stop(self, timeout_seconds: float = 8.0) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout_seconds)

    def health(self) -> dict:
        response = requests.get(f"{self.state.base_url}/health", timeout=5)
        response.raise_for_status()
        return response.json()

    def _wait_until_ready(self, timeout_seconds: float) -> None:
        deadline = time.time() + timeout_seconds
        last_error: Optional[BaseException] = None
        while time.time() < deadline:
            try:
                self.health()
                return
            except Exception as exc:
                last_error = exc
                time.sleep(0.25)
        raise RuntimeError(f"TradeOS backend did not become ready: {last_error}")

    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((self.host, 0))
            return int(sock.getsockname()[1])

