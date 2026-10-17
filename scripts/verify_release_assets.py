"""Validate a draft GitHub release before making its update feed public."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def verify_assets(release: dict, tag: str, checksums: str) -> None:
    if release.get("tag_name") != tag or release.get("draft") is not True:
        raise ValueError("Expected the requested draft release before publication.")
    required = {
        "ShibaClaw-Setup.exe", "ShibaClaw-windows.zip", "releases.win.json",
        f"ShibaClaw-{tag.removeprefix('v')}-full.nupkg", "SHA256SUMS",
        "install.ps1", "install.sh", "update_manifest.json",
    }
    assets = release.get("assets", [])
    by_name = {asset["name"]: asset for asset in assets}
    missing = required - by_name.keys()
    if missing:
        raise ValueError(f"Missing release assets: {', '.join(sorted(missing))}")
    if len(by_name) != len(assets):
        raise ValueError("Duplicate release asset names.")
    for name in required:
        if by_name[name].get("state") != "uploaded":
            raise ValueError(f"Release asset upload is incomplete: {name}")
    for line in checksums.splitlines():
        digest, filename = line.split("  ", 1)
        asset_digest = by_name.get(filename, {}).get("digest", "")
        if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", asset_digest or ""):
            raise ValueError(f"Missing GitHub SHA256 digest for {filename}")
        if asset_digest[7:].lower() != digest.lower():
            raise ValueError(f"Uploaded asset checksum differs from the build: {filename}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--checksums", type=Path, required=True)
    args = parser.parse_args()
    verify_assets(json.load(sys.stdin), args.tag, args.checksums.read_text(encoding="ascii"))
    print("Draft release assets and GitHub SHA256 digests match the build.")


if __name__ == "__main__":
    main()
