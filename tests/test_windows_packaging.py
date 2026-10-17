"""Validate release packaging contracts without freezing or publishing the app."""

import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frontend_errors_stop_windows_build(monkeypatch, tmp_path):
    build = load_script("build_windows")
    webui = tmp_path / "shibaclaw" / "webui"
    webui.mkdir(parents=True)
    (webui / "build.mjs").touch()
    (webui / "node_modules").mkdir()
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build.shutil, "which", lambda _: "node")

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(build.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        build._build_frontend()
    monkeypatch.setattr(build.shutil, "which", lambda _: None)
    with pytest.raises(SystemExit, match="Node.js is required"):
        build._build_frontend()


def test_cli_and_sdk_versions_must_match(monkeypatch):
    packaging = load_script("package_windows")
    monkeypatch.setattr(packaging.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="Velopack CLI 99.0.0,"))
    with pytest.raises(RuntimeError, match="Expected vpk 1.2.161"):
        packaging.validate_tool(Path("vpk.exe"))


def test_setup_feed_webview2_and_portable_archive_contract(monkeypatch, tmp_path):
    packaging = load_script("package_windows")
    onedir = tmp_path / "dist" / "ShibaClaw"
    onedir.mkdir(parents=True)
    (onedir / "ShibaClaw.exe").write_bytes(b"mock desktop exe")
    output = tmp_path / "dist" / "windows-setup"
    captured = []

    def run(command, **kwargs):
        captured.append(command)
        if "pack" not in command:
            return subprocess.CompletedProcess(command, 0, stdout="Velopack CLI 1.2.161, for distributing applications.")
        (output / "ShibaClaw-win-Setup.exe").write_bytes(b"setup")
        filename = "ShibaClaw-1.0.6-full.nupkg"
        (output / filename).write_bytes(b"package")
        (output / "releases.win.json").write_text(json.dumps({"Assets": [{"FileName": filename}]}), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(packaging.subprocess, "run", run)
    artifacts = packaging.package_windows(onedir, output, "1.0.6", Path("vpk.exe"))
    command = captured[-1]
    assert command[command.index("--packId") + 1] == "ShibaClaw"
    assert command[command.index("--framework") + 1] == "webview2"
    assert command[command.index("--channel") + 1] == "win"
    assert "--skipVeloAppCheck" not in command
    with zipfile.ZipFile(tmp_path / "dist" / "ShibaClaw-windows.zip") as archive:
        assert archive.read("ShibaClaw/ShibaClaw.exe") == b"mock desktop exe"
    assert {path.name for path in artifacts} == {
        "ShibaClaw-Setup.exe", "releases.win.json", "ShibaClaw-1.0.6-full.nupkg",
        "ShibaClaw-windows.zip", "SHA256SUMS",
    }
    assert "ShibaClaw-windows.zip" in (output / "SHA256SUMS").read_text()
