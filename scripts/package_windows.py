"""Package the PyInstaller onedir output as Velopack setup and legacy portable ZIP.

The local tool is pinned to the Python SDK version. No install, upload or publishing
occurs. Set Velopack's VPK_SIGN_PARAMS / VPK_SIGN_TEMPLATE only when an existing
code-signing identity is available; otherwise the local artifacts are unsigned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VELOPACK_VERSION = "1.2.161"
PACK_ID = "ShibaClaw"
CHANNEL = "win"
TOOL_DIR = ROOT / "graphify-out" / "validation" / "windows-setup" / "vpk"


def install_tool(tool_dir: Path = TOOL_DIR) -> Path:
    """Install a versioned local .NET tool without changing global tools or PATH."""
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise RuntimeError("The .NET SDK is required to install the local vpk packaging tool.")
    cache_dir = tool_dir.parent
    env = os.environ.copy()
    env.update({
        "DOTNET_CLI_HOME": str(cache_dir / "dotnet-home"),
        "NUGET_PACKAGES": str(cache_dir / "nuget"),
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_GENERATE_ASPNET_CERTIFICATE": "false",
        "DOTNET_ADD_GLOBAL_TOOLS_TO_PATH": "false",
        "DOTNET_NOLOGO": "1",
    })
    subprocess.run([
        dotnet, "tool", "install", "vpk", "--version", VELOPACK_VERSION,
        "--tool-path", str(tool_dir),
    ], check=True, cwd=ROOT, env=env)
    return tool_dir / "vpk.exe"


def validate_tool(vpk: Path) -> None:
    """Reject an accidentally upgraded CLI before creating incompatible packages."""
    result = subprocess.run([str(vpk), "-H"], check=True, capture_output=True, text=True)
    if not re.search(rf"Velopack CLI {re.escape(VELOPACK_VERSION)}(?:\s|,|$)", result.stdout):
        raise RuntimeError(f"Expected vpk {VELOPACK_VERSION}; install the matching local tool.")


def pack_command(vpk: Path, pack_dir: Path, output_dir: Path, version: str) -> list[str]:
    args = [
        str(vpk), "pack", "--packId", PACK_ID, "--packTitle", "ShibaClaw",
        "--packVersion", version, "--packDir", str(pack_dir),
        "--mainExe", "ShibaClaw.exe", "--runtime", "win-x64",
        "--channel", CHANNEL, "--framework", "webview2", "--noPortable",
        "--outputDir", str(output_dir), "--yes", "--skip-updates",
    ]
    icon = ROOT / "assets" / "shibaclaw.ico"
    if icon.is_file():
        args += ["--icon", str(icon)]
    return args


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def package_windows(pack_dir: Path, output_dir: Path, version: str, vpk: Path) -> list[Path]:
    if not (pack_dir / "ShibaClaw.exe").is_file():
        raise RuntimeError(f"Missing PyInstaller onedir executable: {pack_dir / 'ShibaClaw.exe'}")
    validate_tool(vpk)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Keep temporary files on the same volume and inside the writable workspace.
    with tempfile.TemporaryDirectory(prefix=".vpk-", dir=output_dir.parent) as temporary_dir:
        env = {**os.environ, "TEMP": temporary_dir, "TMP": temporary_dir}
        subprocess.run(pack_command(vpk, pack_dir, output_dir, version), check=True, cwd=ROOT, env=env)

    # Keep the original archive name/layout for existing portable downloads and updaters.
    legacy_zip = Path(shutil.make_archive(
        str(output_dir.parent / "ShibaClaw-windows"), "zip", root_dir=pack_dir.parent,
        base_dir=pack_dir.name,
    ))
    setup = output_dir / f"{PACK_ID}-Setup.exe"
    # An explicit channel adds '-win' to vpk's setup filename. Retain that native
    # asset for vpk's assets index and provide the stable public bootstrap URL.
    channel_setup = output_dir / f"{PACK_ID}-{CHANNEL}-Setup.exe"
    if channel_setup.is_file():
        shutil.copy2(channel_setup, setup)
    feed = output_dir / f"releases.{CHANNEL}.json"
    full_packages = sorted(output_dir.glob(f"{PACK_ID}-{version}*-full.nupkg"))
    if not setup.is_file() or not feed.is_file() or not full_packages:
        raise RuntimeError("Velopack did not produce the setup, feed and full update package.")
    assets = json.loads(feed.read_text(encoding="utf-8"))["Assets"]
    for asset in assets:
        filename = asset["FileName"]
        if Path(filename).name != filename or not (output_dir / filename).is_file():
            raise RuntimeError(f"The update feed references a missing package: {filename}")
    artifacts = [setup, feed, *full_packages, *sorted(output_dir.glob("*-delta.nupkg")), legacy_zip]
    # This file helps users verify downloads manually. The bootstrapper trusts GitHub's
    # API asset digest instead, so a substituted checksum file cannot bypass its check.
    checksums = output_dir / "SHA256SUMS"
    checksums.write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in artifacts
    ), encoding="ascii")
    return [*artifacts, checksums]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-dir", type=Path, default=ROOT / "dist" / "ShibaClaw")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "windows-setup")
    parser.add_argument("--version", default=None)
    parser.add_argument("--vpk-path", type=Path, default=TOOL_DIR / "vpk.exe")
    parser.add_argument("--install-tool", action="store_true", help="Install the pinned workspace-local vpk if absent")
    args = parser.parse_args()
    version = args.version or tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        parser.error("--version must be a three-part release version, optionally with a prerelease suffix")
    if args.install_tool and not args.vpk_path.is_file():
        install_tool(args.vpk_path.parent)
    artifacts = package_windows(args.pack_dir.resolve(), args.output_dir.resolve(), version, args.vpk_path.resolve())
    print("Windows setup and update feed are ready (no artifacts were published):")
    for artifact in artifacts:
        print(artifact)


if __name__ == "__main__":
    main()
