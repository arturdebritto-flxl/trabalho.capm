from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(port: int, process: subprocess.Popen[bytes]) -> int:
    url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.monotonic() + 60
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Streamlit encerrou com codigo {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status
        except Exception as exc:  # pragma: no cover - polling loop
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Streamlit nao respondeu em {url}") from last_error


def main() -> int:
    port = _find_free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_app.py",
            "--server.port",
            str(port),
            "--server.headless",
            "true",
            "--server.address",
            "127.0.0.1",
        ]
    )
    try:
        status = _wait_for_health(port, process)
        if status != 200:
            raise RuntimeError(f"Streamlit returned HTTP {status}")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
