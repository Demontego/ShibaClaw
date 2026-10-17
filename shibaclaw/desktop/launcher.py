"""Native Windows launcher for ShibaClaw using pywebview.
Starts the full :class:`~shibaclaw.desktop.runtime.DesktopRuntime`, opens an
embedded WebView window that is auto-authenticated, and wires the window close
button to hide-to-tray behaviour (ready for future pystray integration).
Entry point::
    python -m shibaclaw desktop      # via CLI command added in commands.py
    ShibaClaw.exe                    # frozen PyInstaller build
"""

from __future__ import annotations
import os
import sys
import threading
from pathlib import Path
from typing import Any
from loguru import logger
from shibaclaw.config.paths import get_app_root, get_assets_dir
from shibaclaw.desktop.controller import DesktopController
from shibaclaw.desktop.runtime import DesktopRuntime
from shibaclaw.desktop.window_state import WindowState, load_window_state, save_window_state
from shibaclaw.helpers.system import get_os_type, is_running_as_exe

WINDOWS_APP_USER_MODEL_ID = "RikyZ90.ShibaClaw.Desktop"


def run(
    port: int = 3000,
    host: str = "127.0.0.1",
    config_path: str | None = None,
    workspace: str | None = None,
    with_gateway: bool = True,
    close_policy: str | None = None,
    disable_auth: bool = False,
) -> None:
    """Claim desktop ownership, show the native window, then boot the backend."""
    _configure_desktop_file_logging()
    if get_os_type() != "windows":
        logger.warning(
            "Native launcher is intended for Windows; running anyway on {}", sys.platform
        )
    instance = None
    try:
        if _single_instance_enabled():
            from shibaclaw.desktop.single_instance import WindowsDesktopInstance

            instance = WindowsDesktopInstance(get_app_root())
            if not instance.acquire_or_notify():
                logger.info("Activated the existing ShibaClaw desktop")
                return
        _run_window(
            port=port,
            host=host,
            config_path=config_path,
            workspace=workspace,
            with_gateway=with_gateway,
            close_policy=close_policy,
            disable_auth=disable_auth,
            instance=instance,
        )
    finally:
        if instance is not None:
            instance.close()


def _configure_desktop_file_logging() -> None:
    """Keep startup diagnostics available for the windowed desktop build."""
    try:
        from shibaclaw.config.paths import get_logs_dir

        log_path = get_logs_dir() / "desktop.log"
        logger.add(
            log_path,
            level="DEBUG" if _desktop_debug_enabled() else "INFO",
            rotation="5 MB",
            retention=3,
            encoding="utf-8",
            backtrace=True,
            diagnose=False,
            enqueue=True,
        )
    except OSError as exc:
        logger.error("Could not create the desktop log file: {}", exc)


def _single_instance_enabled() -> bool:
    # Ownership belongs only to the interactive desktop, never CLI/gateway/tests.
    return get_os_type() == "windows" and "PYTEST_CURRENT_TEST" not in os.environ


def _run_window(
    *,
    port: int,
    host: str,
    config_path: str | None,
    workspace: str | None,
    with_gateway: bool,
    close_policy: str | None,
    disable_auth: bool,
    instance: Any,
) -> None:
    _configure_desktop_auth(disable_auth=disable_auth)
    if get_os_type() == "windows":
        _set_windows_app_user_model_id()
    try:
        import webview
    except ImportError:
        print(
            "[ShibaClaw] pywebview is not installed.\n"
            "Install it with:  uv sync --extra desktop\n"
            "or on Windows also:  uv sync --extra desktop --extra windows-native",
            file=sys.stderr,
        )
        sys.exit(1)
    runtime = DesktopRuntime(
        config_path=config_path,
        workspace=workspace,
        port=port,
        host=host,
        with_gateway=with_gateway,
    )
    quit_event = threading.Event()
    shutdown_complete = threading.Event()
    initial_show_complete = threading.Event()
    window_loaded = threading.Event()
    window_shown = threading.Event()

    def _quit_callback() -> None:
        quit_event.set()
        _dispatch_window_action(window, window.destroy, "destroy")

    def _on_loaded(*_args: Any) -> None:
        window_loaded.set()
        startup.on_window_loaded()
        if window_config["start_hidden"] or initial_show_complete.is_set():
            return
        initial_show_complete.set()
        _window_show(window)

    window_config = _resolve_window_config(
        runtime, close_policy, desktop_config=_read_desktop_config(config_path)
    )
    tray = None
    from shibaclaw.desktop.startup import DesktopStartup, startup_html

    window: Any = webview.create_window(
        title="ShibaClaw",
        html=startup_html(),
        width=window_config["width"],
        height=window_config["height"],
        x=window_config["x"],
        y=window_config["y"],
        resizable=True,
        hidden=window_config["start_hidden"],
        frameless=False,
        easy_drag=False,
        text_select=True,
        background_color="#101014",
    )
    controller = DesktopController(
        runtime=runtime,
        window_show=lambda: _window_show(window),
        window_hide=lambda: _window_hide(window),
        quit_callback=_quit_callback,
    )

    def _shutdown_desktop() -> threading.Event:
        controller.quit_app()
        return shutdown_complete

    runtime.set_desktop_shutdown(_shutdown_desktop)
    startup = DesktopStartup(
        runtime,
        controller,
        window,
        quit_event,
        window_ready=window_loaded,
        window_shown=window_shown,
    )
    window.expose(startup.retry, startup.open_logs, startup.quit)
    if window_config.get("start_hidden"):
        controller.window_visible = False
    from shibaclaw.helpers.notification_manager import notification_manager

    def _on_notification(notif: dict[str, Any]) -> None:
        if quit_event.is_set():
            return
        title = notif.get("title") or "ShibaClaw"
        message = notif.get("message")
        if message:
            controller.send_native_notification(title, message)

    notification_manager.add_listener(_on_notification)

    def _on_closing() -> bool:
        """Return False to intercept (cancel) close, True to allow it."""
        if quit_event.is_set():
            return True
        if window_config["close_policy"] == "hide":
            controller.hide_window()
            return False
        controller.quit_app()
        return False

    def _on_resized(width, height):
        save_window_state(
            WindowState(
                width=width,
                height=height,
                x=window.x,
                y=window.y,
            )
        )

    def _on_moved(x, y):
        save_window_state(WindowState(width=window.width, height=window.height, x=x, y=y))

    def _on_start_setup() -> None:
        nonlocal tray
        if instance is not None:
            instance.listen(controller.show_window)
        # pywebview starts this worker while WinForms is still constructing the
        # WebView2 control. Importing PIL/pystray and creating the tray icon at
        # the same time can stall that native startup indefinitely.
        if not window_shown.wait(timeout=30.0) or quit_event.is_set():
            logger.error("Desktop window did not become visible before tray setup")
            return
        logger.debug("Desktop window visible; starting tray and backend")
        from shibaclaw.desktop.tray import HAS_TRAY_DEPS, TrayIcon

        if HAS_TRAY_DEPS:
            tray = TrayIcon(controller)
            controller.set_tray(tray)
            tray.start()
        else:
            logger.debug("Optional tray dependencies missing; tray icon disabled")
            window_config["close_policy"] = "quit"
            window_config["start_hidden"] = False
        startup.start()

    window.events.closing += _on_closing
    window.events.loaded += _on_loaded
    window.events.closed += lambda *_args: quit_event.set()
    window.events.resized += _on_resized
    window.events.moved += _on_moved
    if get_os_type() == "windows":
        def _on_window_shown(*args: Any) -> None:
            window_shown.set()
            logger.debug("Native desktop window shown")

        window.events.shown += _on_window_shown
    logger.info("Opening ShibaClaw window")
    if get_os_type() == "windows":
        os.environ.setdefault(
            "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
            "--disable-gpu-compositing",
        )
    try:
        storage_path = get_app_root() / "desktop" / "webview"
        storage_path.mkdir(parents=True, exist_ok=True)
        webview.start(
            func=_on_start_setup,
            debug=_desktop_debug_enabled(),
            icon=_get_icon_path(),
            gui="edgechromium",
            private_mode=False,
            storage_path=str(storage_path),
        )
    finally:
        quit_event.set()
        try:
            if tray is not None:
                tray.stop()
        finally:
            runtime.stop()
            shutdown_complete.set()


def _refresh_taskbar_icon(window: Any) -> None:
    """Force Windows to refresh the taskbar icon for the given window."""
    import ctypes

    hwnd = _resolve_windows_window_handle(window)
    if not hwnd:
        return
    user32 = ctypes.windll.user32
    swp_framechanged = 0x0020
    swp_nomove = 0x0002
    swp_nosize = 0x0001
    swp_nozorder = 0x0004
    swp_noactivate = 0x0010
    user32.SetWindowPos(
        hwnd,
        None,
        0,
        0,
        0,
        0,
        swp_framechanged | swp_nomove | swp_nosize | swp_nozorder | swp_noactivate,
    )


def _on_shown(window: Any, *_args: Any) -> None:
    """Callback when the window is shown; ensure taskbar icon is set."""
    if get_os_type() == "windows":
        icon_path = _get_windows_icon_path()
        if icon_path:
            _apply_windows_window_icon(window, icon_path)
            _refresh_taskbar_icon(window)


def _window_show(window: Any) -> None:
    def _show_and_focus() -> None:
        window.show()
        if get_os_type() == "windows":
            _focus_windows_window(window)

    _dispatch_window_action(window, _show_and_focus, "show")


def _focus_windows_window(window: Any) -> None:
    """Restore a minimized/hidden desktop and make the native window active."""
    import ctypes
    from ctypes import wintypes

    try:
        hwnd = _resolve_windows_window_handle(window)
        if not hwnd:
            return
        user32 = ctypes.windll.user32
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.IsIconic.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE preserves normal window geometry.
        user32.SetForegroundWindow(hwnd)
        native = getattr(window, "native", None)
        if native is not None:
            native.Activate()
    except Exception as exc:
        logger.debug("Could not focus Windows desktop: {}", exc)


def _window_hide(window: Any) -> None:
    _dispatch_window_action(window, window.hide, "hide")


def _dispatch_window_action(window: Any, action: Any, label: str) -> None:
    """Never wait for pywebview readiness on the WinForms UI thread."""
    shown = getattr(getattr(window, "events", None), "shown", None)
    if shown is not None and callable(getattr(shown, "is_set", None)) and not shown.is_set():
        def _after_shown() -> None:
            if shown.wait(timeout=30.0):
                _dispatch_window_action(window, action, label)
            else:
                logger.warning("Could not {} the desktop window: it was never shown", label)

        threading.Thread(target=_after_shown, name=f"shibaclaw-window-{label}", daemon=True).start()
        return

    def _safe_action() -> None:
        try:
            action()
        except Exception:
            logger.exception("Could not {} the desktop window", label)

    try:
        native = getattr(window, "native", None)
        if native is not None and getattr(native, "InvokeRequired", False):
            import System
            native.BeginInvoke(System.Action(_safe_action))
        else:
            _safe_action()
    except Exception:
        logger.exception("Could not schedule the desktop window {} action", label)


def _desktop_debug_enabled() -> bool:
    """Return True only when desktop debug is explicitly enabled."""
    value = os.environ.get("SHIBACLAW_DESKTOP_DEBUG", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _read_desktop_config(config_path: str | None) -> Any:
    """Read only window preferences, without provider/plugin initialization."""
    import json

    from shibaclaw.config.loader import get_config_path
    from shibaclaw.config.schema import DesktopConfig

    path = Path(config_path).expanduser() if config_path else get_config_path()
    try:
        with path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        return DesktopConfig.model_validate(data.get("desktop", {}))
    except (OSError, ValueError, TypeError, AttributeError):
        return DesktopConfig()


def _resolve_window_config(
    runtime: DesktopRuntime,
    close_policy: str | None,
    *,
    desktop_config: Any = None,
) -> dict[str, Any]:
    """Resolve window geometry and behavior from state file or config defaults."""
    desktop_cfg = desktop_config or (runtime.config.desktop if runtime.config is not None else None)
    default_w = 880
    default_h = 1024
    if desktop_cfg:
        default_w = desktop_cfg.window_width
        default_h = desktop_cfg.window_height
    state = load_window_state(default_w, default_h)
    return {
        "width": state.width,
        "height": state.height,
        "x": state.x,
        "y": state.y,
        "start_hidden": desktop_cfg.start_hidden if desktop_cfg is not None else False,
        "close_policy": close_policy
        or (desktop_cfg.close_behavior if desktop_cfg is not None else "hide"),
    }


def _get_icon_path() -> str | None:
    """Return the absolute path to the application icon if found."""
    assets_dir = get_assets_dir()
    candidates = [
        assets_dir / "shibaclaw.ico",
        assets_dir / "shibaclaw_256.png",
        assets_dir / "shibaclaw_128.png",
        assets_dir / "shibaclaw_64.png",
        assets_dir / "shibaclaw_32.png",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _get_windows_icon_path() -> str | None:
    """Return the .ico asset used for the native Windows window icon."""
    icon_path = get_assets_dir() / "shibaclaw.ico"
    if icon_path.exists():
        return str(icon_path)
    return None


def _set_windows_app_user_model_id() -> None:
    """Set a stable Windows AppUserModelID for taskbar grouping and icon lookup.
    For frozen PyInstaller builds we intentionally skip this step so Windows can
    keep using the embedded .exe icon instead of a generic Python/process icon.
    """
    if get_os_type() != "windows":
        return
    if is_running_as_exe():
        logger.debug("Skipping AppUserModelID on frozen executable to preserve embedded icon")
        return
    import ctypes
    from ctypes import wintypes

    try:
        shell32 = ctypes.windll.shell32
        shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
        shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_int
        shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_USER_MODEL_ID)
    except Exception as exc:
        logger.debug("Could not set Windows AppUserModelID: {}", exc)


def _apply_windows_window_icon(window: Any, icon_path: str) -> None:
    """Apply the icon to the native Windows window and its class.
    The taskbar can still use the generic process icon unless the window class
    and the window handle are both updated. This is especially important for
    the pip/venv launch path, where the process is still the Python launcher.
    """
    import ctypes
    from ctypes import wintypes

    wm_seticon = 0x0080
    icon_small = 0
    icon_big = 1
    image_icon = 1
    lr_loadfromfile = 0x0010
    sm_cxsmicon = 49
    sm_cysmicon = 50
    gcl_hicon = -14
    gcl_hicon_sm = -34
    try:
        import clr

        clr.AddReference("System.Drawing")
        import System.Drawing

        native_window = getattr(window, "native", None)
        if native_window is not None:
            native_window.Icon = System.Drawing.Icon(icon_path)
    except ImportError:
        logger.warning(
            "pythonnet (clr) not installed; cannot use .NET icon set. Taskbar icon may be missing."
        )
    except Exception as exc:
        logger.warning("Failed to set window icon via .NET: {}", exc)
    user32 = ctypes.windll.user32
    hwnd = _resolve_windows_window_handle(window)
    if not hwnd:
        return
    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = wintypes.LPARAM
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    if hasattr(user32, "SetClassLongPtrW"):
        user32.SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        user32.SetClassLongPtrW.restype = ctypes.c_void_p
    big_icon = user32.LoadImageW(None, icon_path, image_icon, 256, 256, lr_loadfromfile)
    small_icon = user32.LoadImageW(
        None,
        icon_path,
        image_icon,
        user32.GetSystemMetrics(sm_cxsmicon),
        user32.GetSystemMetrics(sm_cysmicon),
        lr_loadfromfile,
    )
    if big_icon and hasattr(user32, "SetClassLongPtrW"):
        user32.SetClassLongPtrW(hwnd, gcl_hicon, big_icon)
    if small_icon and hasattr(user32, "SetClassLongPtrW"):
        user32.SetClassLongPtrW(hwnd, gcl_hicon_sm, small_icon)
    if big_icon:
        user32.SendMessageW(hwnd, wm_seticon, icon_big, big_icon)
    if small_icon:
        user32.SendMessageW(hwnd, wm_seticon, icon_small, small_icon)


def _resolve_windows_window_handle(window: Any) -> int | None:
    """Best-effort extraction of the native HWND for a pywebview window."""
    native = getattr(window, "native", None)
    if native is not None:
        for attr_name in ("Handle", "handle"):
            handle = getattr(native, attr_name, None)
            if handle is None:
                continue
            try:
                to_int64 = getattr(handle, "ToInt64", None)
                if callable(to_int64):
                    value = to_int64()
                    return value if isinstance(value, int) else int(str(value))
                return int(handle)
            except (TypeError, ValueError) as e:
                logger.debug("Failed resolving handle attribute {}: {}", attr_name, e)
                continue
    title = getattr(window, "title", None)
    if title:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return int(hwnd)
    return None


def _configure_desktop_auth(*, disable_auth: bool = False) -> None:
    """Configure WebUI auth mode for desktop launches.
    Rules:
    * explicit environment wins;
    * ``disable_auth=True`` forces ``SHIBACLAW_AUTH=false``;
    * local Windows source runs default to auth disabled;
    * frozen/packaged builds keep auth enabled unless explicitly overridden.
    """
    if os.environ.get("SHIBACLAW_AUTH", "").strip():
        logger.debug(
            "Desktop auth mode overridden via SHIBACLAW_AUTH={}", os.environ["SHIBACLAW_AUTH"]
        )
        return
    if disable_auth:
        os.environ["SHIBACLAW_AUTH"] = "false"
        logger.info("Desktop auth disabled explicitly via launcher flag")
        return
    if get_os_type() == "windows" and not is_running_as_exe():
        os.environ["SHIBACLAW_AUTH"] = "false"
        logger.info("Desktop source mode on Windows: SHIBACLAW_AUTH=false")


if __name__ == "__main__":
    run()
