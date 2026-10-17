from pathlib import Path
from types import SimpleNamespace

import pytest

from shibaclaw.desktop import windows_install as install


def test_managed_layout_requires_all_markers(tmp_path):
    current = tmp_path / "current"
    current.mkdir()
    exe = current / "ShibaClaw.exe"
    exe.touch()
    assert install.get_managed_install_root(exe) is None
    (current / "sq.version").touch()
    (tmp_path / "Update.exe").touch()
    assert install.get_managed_install_root(exe) is None
    (tmp_path / "ShibaClaw.exe").touch()
    assert install.get_managed_install_root(exe) == tmp_path
    assert install.get_managed_install_root(tmp_path / "ShibaClaw.exe") is None


def test_source_runtime_never_claims_managed_installation(monkeypatch):
    monkeypatch.setattr(install, "sys", SimpleNamespace(platform="win32", frozen=False))
    assert install.get_managed_install_root() is None


@pytest.fixture
def manager(monkeypatch):
    asset = SimpleNamespace(Version="1.0.7", PackageId="ShibaClaw", NotesMarkdown="New release")
    update = SimpleNamespace(TargetFullRelease=asset, IsDowngrade=False)

    class Manager:
        pending = None
        restart = None
        downloads = 0

        def get_current_version(self):
            return "1.0.6"

        def check_for_updates(self):
            return update

        def get_update_pending_restart(self):
            return self.pending

        def download_updates(self, info, progress):
            self.downloads += 1
            if progress:
                progress(50)
                progress(100)
            self.pending = info.TargetFullRelease

        def wait_exit_then_apply_updates(self, target, **kwargs):
            self.restart = (target, kwargs)

    instance = Manager()
    monkeypatch.setattr(install, "_make_manager", lambda: instance)
    return instance


def test_download_is_separate_from_restart(manager):
    progress = []
    result = install.download_managed_update("1.0.7", lambda value, total: progress.append((value, total)))
    assert result["ok"] and result["ready_to_restart"]
    assert manager.restart is None
    assert progress[-1] == (100, 100)
    assert install.check_managed_update()["ready_to_restart"]
    result = install.prepare_managed_restart("1.0.7")
    assert result["ok"] and result["restart_required"]
    assert manager.restart[1] == {"silent": False, "restart": True, "restart_args": []}


def test_stale_release_cannot_download_a_different_version(manager):
    result = install.download_managed_update("1.0.8")
    assert not result["ok"]
    assert "release changed" in result["output"]
    assert manager.downloads == 0


def test_restart_without_download_does_not_launch_updater(manager):
    assert not install.prepare_managed_restart("1.0.7")["ok"]
    assert manager.restart is None


def test_downloaded_update_remains_available_offline(manager, monkeypatch):
    assert install.download_managed_update("1.0.7")["ok"]

    def offline():
        raise RuntimeError("Network unavailable")

    monkeypatch.setattr(manager, "check_for_updates", offline)
    status = install.check_managed_update()
    assert status["ready_to_restart"] and status["latest"] == "1.0.7"
    assert install.prepare_managed_restart("1.0.7")["ok"]


def test_failed_verification_does_not_report_ready(manager, monkeypatch):
    def corrupt(info, progress):
        raise RuntimeError("Package SHA256 did not match")

    monkeypatch.setattr(manager, "download_updates", corrupt)
    result = install.download_managed_update("1.0.7")
    assert not result["ok"]
    assert "SHA256" in result["output"]
    assert not result.get("ready_to_restart")
    assert manager.restart is None


def test_parallel_update_operation_is_rejected(manager):
    with install._UPDATE_LOCK:
        assert not install.download_managed_update("1.0.7")["ok"]
        assert not install.prepare_managed_restart("1.0.7")["ok"]


def test_managed_checker_exposes_restart_state(manager, monkeypatch):
    from shibaclaw.updater import checker

    monkeypatch.setattr(install, "get_managed_install_root", lambda: Path("managed"))
    install.download_managed_update("1.0.7")
    result = checker._check_exe("1.0.6")
    assert result["managed_install"]
    assert result["ready_to_restart"]
    assert result["action_kind"] == "automatic"
    assert result["manifest_url"] is None


def test_startup_hooks_disable_unattended_apply(monkeypatch):
    import sys

    calls = []

    class App:
        def set_auto_apply_on_startup(self, enabled):
            calls.append(enabled)
            return self

        def run(self):
            calls.append("run")

    monkeypatch.setitem(sys.modules, "velopack", SimpleNamespace(App=App))
    monkeypatch.setattr(install, "sys", SimpleNamespace(platform="win32", frozen=True))
    install.run_startup_hooks()
    assert calls == [False, "run"]
