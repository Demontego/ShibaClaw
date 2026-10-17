"""Small local startup screen and cancellable desktop bootstrap."""

from __future__ import annotations

import base64
import json
import threading
from typing import Any

from loguru import logger

from shibaclaw.config.paths import get_assets_dir


def startup_html() -> str:
    """Return a self-contained screen that works before any local HTTP server."""
    icon = get_assets_dir() / "shibaclaw_128.png"
    try:
        logo = '<img alt="" src="data:image/png;base64,' + base64.b64encode(icon.read_bytes()).decode() + '">'
    except OSError:
        logo = '<span class="fallback" aria-hidden="true">S</span>'
    return _HTML.replace("{{LOGO}}", logo)


class DesktopStartup:
    """Run backend work after the GUI loop starts; expose only recovery actions."""

    def __init__(
        self,
        runtime: Any,
        controller: Any,
        window: Any,
        quitting: threading.Event,
        window_ready: threading.Event | None = None,
        window_shown: threading.Event | None = None,
    ) -> None:
        self._runtime = runtime
        self._controller = controller
        self._window = window
        self._quitting = quitting
        self._busy = threading.Lock()
        self._ready = False
        self._window_ready = window_ready or threading.Event()
        self._window_shown = window_shown or threading.Event()
        if window_shown is None:
            self._window_shown.set()
        if window_ready is None:
            self._window_ready.set()
        self._progress_lock = threading.Lock()
        self._pending_progress: tuple[str, bool] | None = None

    def on_window_loaded(self) -> None:
        """Flush startup progress only after WebView2 can accept JavaScript."""
        with self._progress_lock:
            self._window_ready.set()
            pending = self._pending_progress
            self._pending_progress = None
        if pending is not None:
            self._apply_progress(*pending)

    def start(self) -> None:
        if self._ready or self._quitting.is_set() or not self._busy.acquire(blocking=False):
            return
        try:
            if not self._window_shown.wait(timeout=30.0):
                raise RuntimeError("The desktop window did not become visible in time")
            if self._quitting.is_set():
                return
            self._set_progress("Preparing your workspace…")
            self._runtime.start(on_progress=self._set_progress, cancel_event=self._quitting)
            if self._quitting.is_set():
                self._runtime.stop()
                return
            self._set_progress("Opening your workspace…")
            if not self._runtime.wait_ready(timeout=20.0):
                raise RuntimeError("The local WebUI did not become ready in time")
            if not self._quitting.is_set():
                self._window.load_url(self._runtime.authed_url)
                self._ready = True
        except (Exception, SystemExit):
            logger.exception("Desktop startup failed")
            try:
                self._runtime.stop()
            except Exception:
                logger.exception("Could not fully stop the failed desktop runtime")
            if not self._quitting.is_set():
                self._set_progress(
                    "The local service could not start. Retry, or open the logs for details.",
                    failed=True,
                )
                self._controller.show_window()
        finally:
            self._busy.release()

    def retry(self) -> None:
        if not self._ready and not self._quitting.is_set():
            threading.Thread(target=self.start, name="shibaclaw-startup-retry", daemon=True).start()

    def open_logs(self) -> None:
        self._controller.open_logs()

    def quit(self) -> None:
        self._controller.quit_app()

    def _set_progress(self, message: str, failed: bool = False) -> None:
        if self._quitting.is_set():
            return
        with self._progress_lock:
            if not self._window_ready.is_set():
                self._pending_progress = (message, failed)
                return
        self._apply_progress(message, failed)

    def _apply_progress(self, message: str, failed: bool) -> None:
        if self._quitting.is_set():
            return
        try:
            self._window.evaluate_js(
                f"window.shibaStartup({json.dumps(message)}, {json.dumps(failed)})"
            )
        except Exception as exc:
            logger.debug("Startup screen update unavailable: {}", exc)


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline' 'unsafe-eval'">
<title>ShibaClaw</title><style>
:root{color-scheme:dark;font-family:Segoe UI,system-ui,sans-serif;background:#101014;color:#eeeef3}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;
background:radial-gradient(ellipse at 50% 26%,#29203980,transparent 65%),#101014}
main{width:min(430px,88vw);text-align:center;padding:40px 20px} .logo{width:92px;height:92px;
margin:0 auto 24px;display:grid;place-items:center;border-radius:26px;background:#25212e;
border:1px solid #ffffff12;box-shadow:0 12px 60px #a879fa15}.logo img{width:72px;height:72px;object-fit:contain}
.fallback{font-size:42px;font-weight:700;color:#c49cff}h1{font-size:28px;letter-spacing:-.7px;margin:0 0 9px}
.tagline{margin:0;color:#a6a3b2;font-size:14px}.status{min-height:48px;color:#c7c3d3;font-size:14px;
line-height:1.6;margin:24px 0 18px}.spinner{width:25px;height:25px;margin:36px auto 0;border-radius:50%;
border:2px solid #c29bff22;border-top-color:#bd94f8;animation:spin 1s linear infinite}
.actions{display:flex;justify-content:center;gap:10px;flex-wrap:wrap}.actions[hidden]{display:none}
button{font:inherit;font-size:13px;padding:10px 15px;border-radius:9px;border:1px solid #ffffff22;
background:#27232f;color:#eeeef3;cursor:pointer}button.primary{background:#b98ef3;color:#191122;border-color:transparent;
font-weight:600}button:focus-visible{outline:2px solid #e3cfff;outline-offset:3px}button:hover{filter:brightness(1.12)}
.footnote{margin:40px 0 0;font-size:12px;color:#757181}@keyframes spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.spinner{animation:none}}
</style></head><body><main><div class="logo">{{LOGO}}</div>
<h1>ShibaClaw</h1><p class="tagline">Your personal AI workspace</p>
<div class="spinner" id="spinner" aria-hidden="true"></div>
<p class="status" id="status" role="status" aria-live="polite">Starting ShibaClaw…</p>
<div class="actions" id="actions" hidden>
<button class="primary" onclick="recover('retry')">Try again</button>
<button onclick="recover('open_logs')">Open logs</button><button onclick="recover('quit')">Quit</button>
</div><p class="footnote">Preparing the local service on this computer</p></main>
<script>window.shibaStartup=function(message,failed){document.getElementById('status').textContent=message;
document.getElementById('actions').hidden=!failed;document.getElementById('spinner').hidden=failed;};
function recover(action){if(window.pywebview&&window.pywebview.api){window.pywebview.api[action]();}}
</script></body></html>"""
