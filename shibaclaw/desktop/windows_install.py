"""Windows installation identity and the managed desktop update lifecycle.

The portable executable is deliberately not an installed application. Only a
Velopack installation owns the right to replace its binaries; user data stays
in the existing ShibaClaw data directory, outside ``current``.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Callable

APP_ID = "ShibaClaw"
REPOSITORY_URL = "https://github.com/RikyZ90/ShibaClaw"
SETUP_URL = f"{REPOSITORY_URL}/releases/latest/download/ShibaClaw-Setup.exe"
_UPDATE_LOCK = threading.Lock()


def get_managed_install_root(executable: Path | None = None) -> Path | None:
    """Identify the Velopack layout; explicit paths also support offline checks."""
    if executable is None:
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            return None
        executable = Path(sys.executable)
    executable = executable.resolve()
    current = executable.parent
    root = current.parent
    if (
        executable.name.lower() == "shibaclaw.exe"
        and current.name.lower() == "current"
        and (current / "sq.version").is_file()
        and (root / "Update.exe").is_file()
        and (root / "ShibaClaw.exe").is_file()
    ):
        return root
    return None


def run_startup_hooks() -> None:
    """Run fast installation hooks before importing the desktop application.

    Downloaded updates are applied only after the user requests a restart.
    Gateway subprocesses never call this function.
    """
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    import velopack

    velopack.App().set_auto_apply_on_startup(False).run()


def _make_manager() -> Any:
    if get_managed_install_root() is None:
        raise RuntimeError("This executable is not a managed ShibaClaw installation.")
    import velopack

    # The update source is owned by the application, never supplied by a client.
    manager = velopack.UpdateManager(velopack.GithubSource(REPOSITORY_URL))
    if manager.get_app_id() != APP_ID or manager.get_is_portable():
        raise RuntimeError("The desktop update identity does not match this installation.")
    return manager


def check_managed_update() -> dict[str, Any]:
    with _UPDATE_LOCK:
        manager = _make_manager()
        current = manager.get_current_version()
        pending = manager.get_update_pending_restart()
        # A verified local update remains installable without a network
        # connection, including after the user closes and reopens the app.
        update = manager.check_for_updates() if pending is None else None
        target = update.TargetFullRelease if update else pending
        return {
            "current": current,
            "latest": target.Version if target else current,
            "update_available": target is not None,
            "ready_to_restart": bool(target and pending and pending.Version == target.Version),
            "release_notes": target.NotesMarkdown if target else "",
        }


def download_managed_update(
    version: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Download and verify the official package, without closing the app."""
    if not _UPDATE_LOCK.acquire(blocking=False):
        return {"ok": False, "output": "Another desktop update operation is in progress."}
    try:
        manager = _make_manager()
        update = manager.check_for_updates()
        if update is None or update.TargetFullRelease.Version != version:
            raise RuntimeError("The available release changed. Check for updates again.")
        if update.IsDowngrade or update.TargetFullRelease.PackageId != APP_ID:
            raise RuntimeError("The update does not match this application.")

        def progress(percent: int) -> None:
            if progress_cb:
                progress_cb(max(0, min(100, int(percent))), 100)

        manager.download_updates(update, progress if progress_cb else None)
        pending = manager.get_update_pending_restart()
        if pending is None or pending.Version != version:
            raise RuntimeError("The downloaded update is not ready to install.")
        return {
            "ok": True,
            "ready_to_restart": True,
            "output": "Update downloaded and verified. Restart when you are ready.",
        }
    except Exception as exc:
        return {"ok": False, "output": str(exc)}
    finally:
        _UPDATE_LOCK.release()


def prepare_managed_restart(version: str) -> dict[str, Any]:
    """Arm the updater to wait for a clean desktop exit, then install/restart."""
    if not _UPDATE_LOCK.acquire(blocking=False):
        return {"ok": False, "output": "Another desktop update operation is in progress."}
    try:
        manager = _make_manager()
        pending = manager.get_update_pending_restart()
        if pending is None or pending.Version != version or pending.PackageId != APP_ID:
            raise RuntimeError("Download this update before restarting to install it.")
        # Unlike apply_updates_and_restart, this does not exit the process. The
        # HTTP response is delivered before the registered desktop shutdown runs.
        manager.wait_exit_then_apply_updates(pending, silent=False, restart=True, restart_args=[])
        return {"ok": True, "restart_required": True, "output": "Ready to restart and install the update."}
    except Exception as exc:
        return {"ok": False, "output": str(exc)}
    finally:
        _UPDATE_LOCK.release()
