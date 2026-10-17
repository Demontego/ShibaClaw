"""Apply a ShibaClaw update using the normalized updater contract."""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import re

from loguru import logger

from shibaclaw.updater.detector import PYPI_PACKAGE, get_installation_method
from shibaclaw.updater.manifest import normalize_manifest_path

VERSION_PATTERN = re.compile(r"^[a-zA-Z0-9.\-_]+$")
INSTALLER_URL = "https://github.com/RikyZ90/ShibaClaw/releases/latest/download/install.ps1"


def _old_dir(workspace_root: Path, new_version: str) -> Path:
    """Return the _old/<version>/ directory inside the workspace root."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder = workspace_root / "_old" / f"{date_str}_{new_version}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _pip_upgrade(version: str | None) -> dict[str, Any]:
    """Run a pip upgrade for the requested ShibaClaw version."""
    target = f"{PYPI_PACKAGE}=={version}" if version else PYPI_PACKAGE
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", target]
    if Path("/.dockerenv").exists():
        cmd.insert(-1, "--user")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )

        if result.returncode != 0 and "externally-managed-environment" in result.stderr:
            logger.info("Detected externally-managed-environment during upgrade, retrying with --break-system-packages")
            new_cmd = cmd.copy()
            if "install" in new_cmd:
                idx = new_cmd.index("install")
                new_cmd.insert(idx + 1, "--break-system-packages")

            result = subprocess.run(
                new_cmd,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
            cmd = new_cmd

    except Exception as exc:
        return {"ok": False, "output": str(exc), "command": " ".join(cmd)}

    success = result.returncode == 0
    if success:
        from shibaclaw.updater.checker import invalidate_cache
        invalidate_cache()

    return {
        "ok": success,
        "output": result.stdout + result.stderr,
        "command": " ".join(cmd),
    }


def _backup_personal_files(
    manifest: dict[str, Any] | None,
    workspace_root: Path,
    version: str,
) -> dict[str, Any]:
    """Copy personal files (overwrite=False) to _old/ before applying an update."""
    if not manifest:
        return {"moved": [], "skipped": []}

    old_dir = _old_dir(workspace_root, version or "unknown")
    moved: list[dict[str, str]] = []
    skipped: list[str] = []

    for change in manifest.get("changes", []):
        rel_path = normalize_manifest_path(change.get("path", ""))
        overwrite = change.get("overwrite", True)
        if not rel_path or overwrite:
            if rel_path:
                skipped.append(rel_path)
            continue

        local_file = workspace_root / rel_path
        if not local_file.exists():
            skipped.append(rel_path)
            continue

        dest = old_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_file, dest)
        moved.append({"from": str(local_file), "to": str(dest)})

    return {"moved": moved, "skipped": skipped}


def _normalize_update_request(
    update_info: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = dict(update_info or {})
    install_method = normalized.get("install_method") or get_installation_method()
    latest = normalized.get("latest") or (manifest or {}).get("version")

    normalized.setdefault("install_method", install_method)
    normalized.setdefault("latest", latest)

    if install_method in ("pip", "exe"):
        normalized.setdefault("action_kind", "automatic")
    else:
        normalized.setdefault("action_kind", "manual-command")
    normalized.setdefault(
        "action_label",
        "Update now" if install_method in ("pip", "exe") else "Run suggested update command",
    )

    default_cmd = "git pull --ff-only && pip install -e ."
    if install_method == "pip":
        default_cmd = "pip install --upgrade shibaclaw"
    elif install_method == "exe":
        default_cmd = (
            f'powershell -c "irm {INSTALLER_URL} | iex"'
        )

    normalized.setdefault("action_command", default_cmd)
    return normalized


def _manual_report(update_info: dict[str, Any], version: str) -> dict[str, Any]:
    install_method = update_info.get("install_method") or "source"
    action_target = update_info.get("action_command") or update_info.get("action_url")
    message = update_info.get("summary") or "This update must be applied manually."
    if action_target:
        message = f"{message} Suggested action: {action_target}"

    return {
        "install_method": install_method,
        "version": version,
        "requires_manual_action": True,
        "restarting": False,
        "action_kind": update_info.get("action_kind"),
        "action_label": update_info.get("action_label"),
        "action_command": update_info.get("action_command"),
        "action_url": update_info.get("action_url") or update_info.get("release_url"),
        "message": message,
        "backup": {"moved": [], "skipped": []},
        "pip": None,
    }


def apply_update(
    update_info: dict[str, Any] | None,
    workspace_root: Path,
    *,
    manifest: dict[str, Any] | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Apply an update or return a manual-action report for non-pip/non-exe installs."""
    normalized = _normalize_update_request(update_info, manifest)
    if get_installation_method() == "exe":
        normalized["install_method"] = "exe"
    install_method = normalized["install_method"]
    version = normalized.get("latest") or (manifest or {}).get("version") or "unknown"

    if not VERSION_PATTERN.match(version) or ".." in version:
        return {
            "install_method": install_method,
            "version": version,
            "requires_manual_action": False,
            "restarting": False,
            "action_kind": normalized.get("action_kind"),
            "action_label": normalized.get("action_label"),
            "action_command": normalized.get("action_command"),
            "action_url": normalized.get("action_url") or normalized.get("release_url"),
            "message": f"Failed to update ShibaClaw to {version}: Invalid version format.",
            "pip": None,
            "exe": {"ok": False, "output": "Invalid version format"},
            "backup": {"moved": [], "skipped": []},
        }

    if install_method not in ("pip", "exe") or normalized.get("action_kind") != "automatic":
        return _manual_report(normalized, version)

    if install_method == "exe":
        from shibaclaw.desktop.windows_install import (
            SETUP_URL, download_managed_update, get_managed_install_root, prepare_managed_restart,
        )

        # Portable/legacy executables never replace themselves or execute a
        # client-provided URL. Migration uses the same setup as a fresh install.
        if get_managed_install_root() is None:
            return _manual_report({
                **normalized,
                "action_kind": "manual-url",
                "action_command": None,
                "action_url": SETUP_URL,
                "action_label": "Download Windows setup",
                "summary": "Install the Windows setup to enable managed updates. Your existing data is preserved.",
            }, version)
        phase = normalized.get("phase", "download")
        if phase == "download":
            apply_result = download_managed_update(version, progress_cb)
        elif phase == "restart":
            apply_result = prepare_managed_restart(version)
        else:
            apply_result = {"ok": False, "output": "Invalid desktop update phase."}
        if apply_result.get("ok"):
            from shibaclaw.updater.checker import invalidate_cache
            invalidate_cache()
        return {
            "install_method": "exe",
            "version": version,
            "requires_manual_action": False,
            "restarting": False,
            "ready_to_restart": bool(apply_result.get("ready_to_restart")),
            "action_kind": "automatic",
            "message": apply_result.get("output", "Desktop update failed."),
            "pip": None,
            "exe": apply_result,
            "backup": {"moved": [], "skipped": []},
        }

    backup = _backup_personal_files(manifest, workspace_root, version)
    apply_result = _pip_upgrade(version)

    message = (
        f"Updated ShibaClaw to {version}."
        if apply_result.get("ok")
        else f"Failed to update ShibaClaw to {version}."
    )

    return {
        "install_method": install_method,
        "version": version,
        "requires_manual_action": False,
        "restarting": False,
        "action_kind": normalized.get("action_kind"),
        "action_label": normalized.get("action_label"),
        "action_command": normalized.get("action_command"),
        "action_url": normalized.get("action_url") or normalized.get("release_url"),
        "message": message,
        "pip": apply_result if install_method == "pip" else None,
        "exe": apply_result if install_method == "exe" else None,
        "backup": backup,
    }
