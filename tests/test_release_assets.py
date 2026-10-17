import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("verify_release_assets", Path(__file__).resolve().parents[1] / "scripts/verify_release_assets.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def draft():
    names = ["ShibaClaw-Setup.exe", "ShibaClaw-windows.zip", "releases.win.json", "ShibaClaw-1.0.7-full.nupkg", "SHA256SUMS", "install.ps1", "install.sh", "update_manifest.json"]
    return {"tag_name": "v1.0.7", "draft": True, "assets": [
        {"name": name, "state": "uploaded", "digest": "sha256:" + "a" * 64} for name in names
    ]}


def test_complete_draft_can_be_published(draft):
    release.verify_assets(draft, "v1.0.7", "a" * 64 + "  ShibaClaw-Setup.exe\n")


def test_incomplete_feed_cannot_be_published(draft):
    draft["assets"] = [a for a in draft["assets"] if a["name"] != "releases.win.json"]
    with pytest.raises(ValueError, match="Missing release assets"):
        release.verify_assets(draft, "v1.0.7", "")


def test_digest_required_by_powershell_is_verified_before_publication(draft):
    draft["assets"][0]["digest"] = None
    with pytest.raises(ValueError, match="Missing GitHub SHA256"):
        release.verify_assets(draft, "v1.0.7", "a" * 64 + "  ShibaClaw-Setup.exe\n")


def test_substituted_upload_cannot_be_published(draft):
    with pytest.raises(ValueError, match="differs from the build"):
        release.verify_assets(draft, "v1.0.7", "b" * 64 + "  ShibaClaw-Setup.exe\n")
