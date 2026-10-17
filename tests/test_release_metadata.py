import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_release", ROOT / "scripts/verify_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.7"\n', encoding="utf-8")
    (tmp_path / "uv.lock").write_text('[[package]]\nname = "shibaclaw"\nversion = "1.0.7"\n', encoding="utf-8")
    for path in ("shibaclaw/updater/update_manifest.json", "shibaclaw/webui/package.json"):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"version": "1.0.7"}), encoding="utf-8")
    target = tmp_path / "shibaclaw/desktop/app.manifest"
    target.parent.mkdir(parents=True)
    target.write_text('<assembly xmlns="urn:schemas-microsoft-com:asm.v1"><assemblyIdentity version="1.0.7.0"/></assembly>', encoding="utf-8")
    return tmp_path


def test_matching_release_can_proceed(project):
    assert release.verify_release(project, "v1.0.7") == "1.0.7"


def test_wrong_tag_is_rejected_before_publishing(project):
    with pytest.raises(ValueError, match="Release tag"):
        release.verify_release(project, "v1.0.8")


@pytest.mark.parametrize("filename", [
    "update_manifest.json", "shibaclaw/updater/update_manifest.json", "shibaclaw/webui/package.json",
])
def test_stale_packaged_version_is_rejected(project, filename):
    (project / filename).write_text(json.dumps({"version": "1.0.6"}), encoding="utf-8")
    with pytest.raises(ValueError, match=filename):
        release.verify_release(project, "v1.0.7")


def test_stale_lock_and_windows_identity_are_rejected(project):
    (project / "uv.lock").write_text('[[package]]\nname = "shibaclaw"\nversion = "1.0.6"\n', encoding="utf-8")
    target = project / "shibaclaw/desktop/app.manifest"
    target.write_text(target.read_text().replace("1.0.7.0", "1.0.6.0"), encoding="utf-8")
    with pytest.raises(ValueError) as error:
        release.verify_release(project)
    assert "uv.lock" in str(error.value) and "app.manifest" in str(error.value)
