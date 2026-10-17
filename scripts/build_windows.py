"""Build the Windows desktop onedir bundle with PyInstaller."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PKG_RESOURCES_WARNING_FILTER = (
    "ignore:pkg_resources is deprecated as an API:UserWarning"
)


def _sync_packaged_update_manifest() -> None:
    """Keep the bundled updater manifest in sync with the repo root manifest."""
    source_manifest = ROOT / "update_manifest.json"
    packaged_manifest = ROOT / "shibaclaw" / "updater" / "update_manifest.json"

    if source_manifest.exists():
        packaged_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_manifest, packaged_manifest)


def _check_build_environment() -> None:
    if sys.version_info < (3, 12):
        raise SystemExit(
            "Windows desktop packaging requires Python 3.12 or newer."
        )

    missing = []
    for module_name in ("PyInstaller", "PIL", "pystray", "webview"):
        try:
            __import__(module_name)
        except ImportError:
            import traceback
            print(f"Error importing {module_name}:")
            traceback.print_exc()
            missing.append(module_name)

    if missing:
        raise SystemExit(
            "Missing desktop build dependencies: "
            + ", ".join(missing)
            + ". Install them with: uv sync --extra desktop --extra windows-native --extra dev --extra rag"
        )


def _build_frontend() -> None:
    webui_dir = ROOT / "shibaclaw" / "webui"
    if (webui_dir / "build.mjs").exists():
        print("Building WebUI frontend assets...")
        if not shutil.which("node"):
            raise SystemExit("Node.js is required to build the Windows frontend assets.")
        if not (webui_dir / "node_modules").exists():
            npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
            if not npm:
                raise SystemExit("npm is required to install the frontend build dependencies.")
            subprocess.run([npm, "ci"], check=True, cwd=webui_dir)
        subprocess.run(["node", "build.mjs"], check=True, cwd=webui_dir)


def main() -> None:
    _check_build_environment()
    _sync_packaged_update_manifest()
    _build_frontend()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_icons.py")], check=True, cwd=ROOT)

    pyinstaller_env = os.environ.copy()
    current_filters = pyinstaller_env.get("PYTHONWARNINGS", "")
    if _PKG_RESOURCES_WARNING_FILTER not in current_filters:
        pyinstaller_env["PYTHONWARNINGS"] = (
            f"{_PKG_RESOURCES_WARNING_FILTER},{current_filters}"
            if current_filters
            else _PKG_RESOURCES_WARNING_FILTER
        )

    subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(ROOT / "shibaclaw.spec"), "--noconfirm", "--clean"],
        check=True,
        cwd=ROOT,
        env=pyinstaller_env,
    )


if __name__ == "__main__":
    main()
