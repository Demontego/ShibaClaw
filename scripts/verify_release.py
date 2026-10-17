"""Fail before publishing when the tag and packaged versions disagree."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify_release(root: Path, tag: str | None = None) -> str:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    errors = []
    if tag is not None and tag != f"v{version}":
        errors.append(f"Release tag {tag!r} must match pyproject.toml version v{version}.")
    surfaces = {
        "shibaclaw/updater/update_manifest.json": "version",
        "shibaclaw/webui/package.json": "version",
    }
    # The root manifest is retained by older checkouts, but is optional in a
    # clean checkout. When present it is copied into the Windows bundle.
    if (root / "update_manifest.json").is_file():
        surfaces["update_manifest.json"] = "version"
    for filename, key in surfaces.items():
        actual = json.loads((root / filename).read_text(encoding="utf-8")).get(key)
        if actual != version:
            errors.append(f"{filename}: expected {version}, got {actual!r}.")
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    locked = [p["version"] for p in lock["package"] if p["name"] == "shibaclaw"]
    if locked != [version]:
        errors.append(f"uv.lock: expected one shibaclaw {version}, got {locked!r}.")
    identity = ET.parse(root / "shibaclaw/desktop/app.manifest").getroot().find(
        "{urn:schemas-microsoft-com:asm.v1}assemblyIdentity"
    )
    numeric = re.match(r"\d+\.\d+\.\d+", version)
    expected = f"{numeric.group()}.0" if numeric else None
    actual = identity.get("version") if identity is not None else None
    if actual != expected or expected is None:
        errors.append(f"Windows app.manifest: expected {expected}, got {actual!r}.")
    if errors:
        raise ValueError("Release metadata is inconsistent:\n" + "\n".join(errors))
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Exact tag to publish, including its v prefix")
    args = parser.parse_args()
    print(f"Release metadata verified: {verify_release(ROOT, args.tag)}")


if __name__ == "__main__":
    main()
