from pathlib import Path


def test_apply_update_returns_manual_report_for_docker(tmp_path):
    from shibaclaw.updater.apply import apply_update

    report = apply_update(
        {
            "install_method": "docker",
            "latest": "0.3.8",
            "action_kind": "manual-command",
            "action_label": "Pull latest image",
            "action_command": "docker pull rikyz90/shibaclaw:latest",
        },
        tmp_path,
    )

    assert report["requires_manual_action"] is True
    assert report["restarting"] is False
    assert report["pip"] is None
    assert "docker pull" in report["message"]


def test_apply_update_runs_backup_and_pip_for_pip(tmp_path, monkeypatch):
    from shibaclaw.updater import apply

    personal_file = tmp_path / "USER.md"
    personal_file.write_text("customized\n", encoding="utf-8")
    manifest = {
        "version": "0.3.8",
        "changes": [
            {"path": "USER.md", "overwrite": False},
            {"path": "skills/memory/SKILL.md", "overwrite": True},
        ],
    }
    monkeypatch.setattr(apply, "_pip_upgrade", lambda version: {"ok": True, "output": f"updated {version}"})

    report = apply.apply_update(
        {"install_method": "pip", "latest": "0.3.8", "action_kind": "automatic"},
        tmp_path,
        manifest=manifest,
    )

    assert report["requires_manual_action"] is False
    assert report["pip"]["ok"] is True
    assert report["backup"]["moved"]
    backup_target = Path(report["backup"]["moved"][0]["to"])
    assert backup_target.exists()
    assert backup_target.read_text(encoding="utf-8") == "customized\n"


def test_apply_update_supports_manifest_only_payload(tmp_path, monkeypatch):
    from shibaclaw.updater import apply

    monkeypatch.setattr(apply, "get_installation_method", lambda: "pip")
    monkeypatch.setattr(apply, "_pip_upgrade", lambda version: {"ok": True, "output": version})

    report = apply.apply_update(None, tmp_path, manifest={"version": "0.3.9", "changes": []})

    assert report["version"] == "0.3.9"
    assert report["pip"]["output"] == "0.3.9"


def test_managed_exe_download_preserves_personal_files(tmp_path, monkeypatch):
    from shibaclaw.desktop import windows_install
    from shibaclaw.updater import apply

    personal = tmp_path / "USER.md"
    personal.write_text("keep me", encoding="utf-8")
    monkeypatch.setattr(windows_install, "get_managed_install_root", lambda: tmp_path)
    monkeypatch.setattr(windows_install, "download_managed_update", lambda version, cb: {
        "ok": True, "ready_to_restart": True, "output": "Downloaded; restart later.",
    })
    report = apply.apply_update({
        "install_method": "exe", "latest": "1.0.7", "action_kind": "automatic",
        "action_url": "https://untrusted.invalid/ignored.exe",
    }, tmp_path, manifest={"changes": [{"path": "USER.md", "overwrite": False}]})
    assert report["exe"]["ok"]
    assert report["ready_to_restart"]
    assert not report["restarting"]
    assert report["backup"]["moved"] == []
    assert personal.read_text(encoding="utf-8") == "keep me"
    assert not (tmp_path / "_old").exists()
    assert "Updated ShibaClaw" not in report["message"]


def test_legacy_exe_never_executes_a_download_url(tmp_path, monkeypatch):
    from shibaclaw.desktop import windows_install
    from shibaclaw.updater import apply

    monkeypatch.setattr(windows_install, "get_managed_install_root", lambda: None)
    report = apply.apply_update({
        "install_method": "exe", "latest": "1.0.7", "action_kind": "automatic",
        "action_url": "https://untrusted.invalid/payload.exe",
    }, tmp_path)
    assert report["requires_manual_action"]
    assert report["action_url"] == windows_install.SETUP_URL
    assert report["action_kind"] == "manual-url"


def test_managed_exe_restart_requires_explicit_phase(tmp_path, monkeypatch):
    from shibaclaw.desktop import windows_install
    from shibaclaw.updater import apply

    monkeypatch.setattr(windows_install, "get_managed_install_root", lambda: tmp_path)
    monkeypatch.setattr(windows_install, "prepare_managed_restart", lambda version: {
        "ok": True, "restart_required": True, "output": "Restart prepared.",
    })
    report = apply.apply_update({
        "install_method": "exe", "latest": "1.0.7", "action_kind": "automatic", "phase": "restart",
    }, tmp_path)
    assert report["exe"]["restart_required"]
    assert "Updated ShibaClaw" not in report["message"]


def test_apply_update_invalid_version_fails(tmp_path):
    from shibaclaw.updater.apply import apply_update

    for bad_version in ["../bad", "1.0.0; calc", "1.0.0\\path", "v1.0..0"]:
        report = apply_update(
            {
                "install_method": "pip",
                "latest": bad_version,
                "action_kind": "automatic",
            },
            tmp_path,
        )
        assert report["requires_manual_action"] is False
        assert report["exe"]["ok"] is False
        assert "Invalid version format" in report["exe"]["output"]


