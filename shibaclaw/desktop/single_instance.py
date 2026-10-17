"""Windows desktop ownership and activation, independent of gateway ports."""

from __future__ import annotations

import ctypes
import hashlib
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Callable

from loguru import logger


class WindowsDesktopInstance:
    """Keep one desktop per user/session and signal it on subsequent launches.

    Named kernel objects disappear automatically when the process exits. The
    auto-reset event also preserves an activation that arrives before the GUI
    starts, so a second launch during startup is not lost.
    """

    def __init__(self, data_root: Path) -> None:
        identity = hashlib.sha256(str(data_root.resolve()).casefold().encode()).hexdigest()[:24]
        self._name = rf"Local\ShibaClaw.Desktop.{identity}"
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._mutex = None
        self._event = None
        self._closed = threading.Event()
        self._thread: threading.Thread | None = None
        self._configure_api()

    def _configure_api(self) -> None:
        api = self._kernel32
        api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        api.CreateMutexW.restype = wintypes.HANDLE
        api.CreateEventW.argtypes = [
            ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR
        ]
        api.CreateEventW.restype = wintypes.HANDLE
        api.SetEvent.argtypes = [wintypes.HANDLE]
        api.SetEvent.restype = wintypes.BOOL
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.WaitForSingleObject.restype = wintypes.DWORD
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL

    def acquire_or_notify(self) -> bool:
        """Return True for the owner; otherwise activate the existing owner."""
        try:
            # Create the event before claiming ownership to close the startup race.
            self._event = self._kernel32.CreateEventW(None, False, False, self._name + ".Activate")
            if not self._event:
                raise ctypes.WinError(ctypes.get_last_error())
            self._mutex = self._kernel32.CreateMutexW(None, False, self._name)
            error = ctypes.get_last_error()
            if not self._mutex:
                raise ctypes.WinError(error)
            if error != 183:  # ERROR_ALREADY_EXISTS
                return True
            _allow_existing_window_foreground()
            if not self._kernel32.SetEvent(self._event):
                raise ctypes.WinError(ctypes.get_last_error())
            return False
        except BaseException:
            self.close()
            raise

    def listen(self, activate: Callable[[], None]) -> None:
        """Start activation handling once the native window is available."""
        if self._thread is not None or self._event is None:
            return

        def _listen() -> None:
            while not self._closed.is_set():
                result = self._kernel32.WaitForSingleObject(self._event, 250)
                if self._closed.is_set():
                    break
                if result == 0:  # WAIT_OBJECT_0
                    try:
                        activate()
                    except Exception as exc:
                        logger.debug("Could not activate desktop window: {}", exc)
                elif result != 258:  # WAIT_TIMEOUT
                    logger.warning("Desktop activation listener stopped (Win32 result {})", result)
                    break

        self._thread = threading.Thread(target=_listen, name="shibaclaw-activation", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._closed.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        self._thread = None
        for name in ("_mutex", "_event"):
            handle = getattr(self, name)
            if handle is not None:
                self._kernel32.CloseHandle(handle)
                setattr(self, name, None)


def _allow_existing_window_foreground() -> None:
    """Pass foreground permission from the new launch to the existing GUI."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
    user32.AllowSetForegroundWindow.restype = wintypes.BOOL
    hwnd = user32.FindWindowW(None, "ShibaClaw")
    if hwnd:
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value:
            user32.AllowSetForegroundWindow(process_id.value)
