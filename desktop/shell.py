"""
Desktop launcher: starts uvicorn in a background thread, then opens the app
in a native pywebview window. Requires WebView2 runtime on Windows.
"""
import sys
import threading
import time

import uvicorn
import webview

_PORT = 8756
_HOST = "127.0.0.1"


def _start_backend() -> None:
    sys.path.insert(0, str(__file__).replace("desktop/shell.py", "backend"))
    from app.main import app  # noqa: PLC0415

    uvicorn.run(app, host=_HOST, port=_PORT, log_level="warning")


if __name__ == "__main__":
    t = threading.Thread(target=_start_backend, daemon=True)
    t.start()
    time.sleep(2)  # allow uvicorn to bind before opening window
    webview.create_window("Dealer CRM", f"http://{_HOST}:{_PORT}", width=1280, height=800)
    webview.start()
