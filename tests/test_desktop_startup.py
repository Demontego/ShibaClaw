"""Desktop boot/activation regressions without user data or a real gateway."""

from __future__ import annotations

import os
import sys
import threading
import types
from unittest import mock

import pytest

from shibaclaw.config.schema import DesktopConfig
from shibaclaw.desktop.runtime import DesktopRuntime
from shibaclaw.desktop.startup import DesktopStartup, startup_html


class _Event:
    def __init__(self):
        self.callbacks = []

    def __iadd__(self, callback):
        self.callbacks.append(callback)
        return self


def _window():
    window = mock.Mock()
    window.native = None
    window.events = types.SimpleNamespace(**{
        name: _Event()
        for name in ("loaded", "closing", "closed", "before_show", "resized", "moved", "shown")
    })
    return window


@pytest.mark.parametrize("tray_available", [False, True])
def test_shell_opens_before_backend_and_keeps_webview_data_outside_binaries(tmp_path, tray_available):
    from shibaclaw.desktop import launcher
    from shibaclaw.desktop.window_state import WindowState

    runtime = mock.Mock(config=None, authed_url="http://127.0.0.1:3030/?desktop-auth")
    runtime.wait_ready.return_value = True
    window = _window()
    webview = mock.Mock()

    def create_window(**kwargs):
        runtime.start.assert_not_called()
        assert "Starting ShibaClaw" in kwargs["html"]
        assert "url" not in kwargs
        assert kwargs["hidden"] is False
        return window

    def start(**kwargs):
        tray_module.TrayIcon.assert_not_called()
        for callback in window.events.shown.callbacks:
            callback()
        runtime.start.assert_not_called()
        kwargs["func"]()
        show_window.assert_not_called()

    webview.create_window.side_effect = create_window
    webview.start.side_effect = start
    tray_module = types.SimpleNamespace(HAS_TRAY_DEPS=tray_available, TrayIcon=mock.Mock())
    with (
        mock.patch.dict(sys.modules, {"webview": webview, "shibaclaw.desktop.tray": tray_module}),
        mock.patch.object(launcher, "DesktopRuntime", return_value=runtime),
        mock.patch.object(launcher, "get_os_type", return_value="windows"),
        mock.patch.object(launcher, "_single_instance_enabled", return_value=False),
        mock.patch.object(launcher, "_set_windows_app_user_model_id"),
        mock.patch.object(launcher, "get_app_root", return_value=tmp_path),
        mock.patch.object(launcher, "_read_desktop_config", return_value=DesktopConfig()),
        mock.patch.object(launcher, "load_window_state", return_value=WindowState(920, 1048)),
        mock.patch.object(launcher, "_window_show") as show_window,
        mock.patch.object(launcher, "_get_windows_icon_path", return_value=None),
    ):
        launcher.run(port=3030)

    runtime.start.assert_called_once()
    window.load_url.assert_called_once_with(runtime.authed_url)
    runtime.stop.assert_called_once()
    assert webview.start.call_args.kwargs["storage_path"] == str(tmp_path / "desktop" / "webview")
    assert webview.start.call_args.kwargs["gui"] == "edgechromium"
    if tray_available:
        tray_module.TrayIcon.assert_called_once()
        tray_module.TrayIcon.return_value.start.assert_called_once()
        tray_module.TrayIcon.return_value.stop.assert_called_once()
    else:
        tray_module.TrayIcon.assert_not_called()


def test_second_windows_launch_activates_owner_without_starting_runtime(tmp_path):
    from shibaclaw.desktop import launcher, single_instance

    instance = mock.Mock()
    instance.acquire_or_notify.return_value = False
    with (
        mock.patch.object(launcher, "_single_instance_enabled", return_value=True),
        mock.patch.object(launcher, "get_app_root", return_value=tmp_path),
        mock.patch.object(single_instance, "WindowsDesktopInstance", return_value=instance),
        mock.patch.object(launcher, "_run_window") as run_window,
    ):
        launcher.run()
    run_window.assert_not_called()
    instance.close.assert_called_once()


def test_instance_is_released_if_window_creation_fails(tmp_path):
    from shibaclaw.desktop import launcher, single_instance

    instance = mock.Mock()
    instance.acquire_or_notify.return_value = True
    with (
        mock.patch.object(launcher, "_single_instance_enabled", return_value=True),
        mock.patch.object(launcher, "get_app_root", return_value=tmp_path),
        mock.patch.object(single_instance, "WindowsDesktopInstance", return_value=instance),
        mock.patch.object(launcher, "_run_window", side_effect=RuntimeError("WebView2 failed")),
    ):
        with pytest.raises(RuntimeError, match="WebView2"):
            launcher.run()
    instance.close.assert_called_once()


def test_startup_failure_is_visible_and_can_be_retried():
    runtime = mock.Mock(authed_url="http://127.0.0.1:3000/?auth")
    runtime.start.side_effect = [RuntimeError("provider unavailable"), None]
    runtime.wait_ready.return_value = True
    controller = mock.Mock()
    window = mock.Mock()
    startup = DesktopStartup(runtime, controller, window, threading.Event())

    startup.start()
    runtime.stop.assert_called_once()
    window.load_url.assert_not_called()
    controller.show_window.assert_called_once()
    assert "could not start" in window.evaluate_js.call_args.args[0]
    assert "provider unavailable" not in window.evaluate_js.call_args.args[0]
    startup.start()
    window.load_url.assert_called_once_with(runtime.authed_url)
    startup.start()
    assert runtime.start.call_count == 2


def test_startup_progress_waits_until_webview_page_is_loaded():
    runtime = mock.Mock(authed_url="http://127.0.0.1:3000/?auth")
    runtime.start.side_effect = RuntimeError("provider unavailable")
    controller = mock.Mock()
    window = mock.Mock()
    window_ready = threading.Event()
    startup = DesktopStartup(
        runtime,
        controller,
        window,
        threading.Event(),
        window_ready=window_ready,
    )

    startup.start()

    window.evaluate_js.assert_not_called()
    startup.on_window_loaded()
    assert "could not start" in window.evaluate_js.call_args.args[0]


def test_startup_waits_for_native_window_before_starting_backend():
    runtime = mock.Mock(authed_url="http://127.0.0.1:3000/?auth")
    runtime.wait_ready.return_value = True
    window_shown = threading.Event()
    controller = mock.Mock()
    window = mock.Mock()
    startup = DesktopStartup(
        runtime,
        controller,
        window,
        threading.Event(),
        window_shown=window_shown,
    )

    worker = threading.Thread(target=startup.start)
    worker.start()
    runtime.start.assert_not_called()
    window_shown.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    runtime.start.assert_called_once()
    window.load_url.assert_called_once_with(runtime.authed_url)


def test_wait_ready_timeout_does_not_load_an_unavailable_page():
    runtime = mock.Mock()
    runtime.wait_ready.return_value = False
    controller = mock.Mock()
    window = mock.Mock()
    DesktopStartup(runtime, controller, window, threading.Event()).start()
    window.load_url.assert_not_called()
    runtime.stop.assert_called_once()
    controller.show_window.assert_called_once()


def test_quit_during_startup_does_not_navigate_or_show_an_error():
    quitting = threading.Event()
    runtime = mock.Mock()
    runtime.start.side_effect = lambda **kwargs: quitting.set()
    window = mock.Mock()
    controller = mock.Mock()
    DesktopStartup(runtime, controller, window, quitting).start()
    runtime.stop.assert_called_once()
    runtime.wait_ready.assert_not_called()
    window.load_url.assert_not_called()
    controller.show_window.assert_not_called()


def test_runtime_cleans_gateway_when_server_start_raises_and_allows_retry():
    runtime = DesktopRuntime()
    with (
        mock.patch.object(runtime, "_load_config"),
        mock.patch.object(runtime, "_start_gateway") as gateway_start,
        mock.patch.object(runtime, "_start_server", side_effect=[RuntimeError("bind failed"), None]),
        mock.patch.object(runtime, "_stop_gateway") as gateway_stop,
        mock.patch.object(runtime, "_stop_server") as server_stop,
    ):
        with pytest.raises(RuntimeError, match="bind failed"):
            runtime.start()
        gateway_stop.assert_called_once()
        server_stop.assert_called_once()
        runtime.start()
    assert gateway_start.call_count == 2
    assert runtime._stopping is False


def test_runtime_avoids_another_service_on_the_default_webui_port():
    runtime = DesktopRuntime(port=3000)
    seen_webui_urls = []
    with (
        mock.patch.object(runtime, "_load_config"),
        mock.patch.object(
            runtime,
            "_start_gateway",
            side_effect=lambda: seen_webui_urls.append(runtime.base_url),
        ),
        mock.patch.object(runtime, "_start_server"),
        mock.patch("shibaclaw.desktop.runtime.is_tcp_port_available", return_value=False),
        mock.patch("shibaclaw.desktop.runtime.find_free_tcp_port", return_value=43127),
        mock.patch.dict(os.environ, {}, clear=False),
    ):
        runtime.start()

    assert runtime.base_url == "http://127.0.0.1:43127"
    assert seen_webui_urls == ["http://127.0.0.1:43127"]


def test_runtime_does_not_start_after_external_cancellation():
    quitting = threading.Event()
    quitting.set()
    runtime = DesktopRuntime()
    with mock.patch.object(runtime, "_load_config") as load:
        with pytest.raises(RuntimeError, match="cancelled"):
            runtime.start(cancel_event=quitting)
    load.assert_not_called()


def test_stop_interrupts_gateway_startup_wait_and_leaves_no_child():
    from shibaclaw.config.schema import Config

    runtime = DesktopRuntime()
    proc = mock.Mock()
    proc.poll.return_value = None
    reached_health_check = threading.Event()

    def not_ready(*args):
        reached_health_check.set()
        return False

    def load_config():
        runtime.config = Config()

    failures = []

    def start():
        try:
            runtime.start()
        except RuntimeError as exc:
            failures.append(str(exc))

    with (
        mock.patch.object(runtime, "_load_config", side_effect=load_config),
        mock.patch.object(runtime, "_resolve_gateway_ports", return_value=(19900, 19901)),
        mock.patch.object(runtime, "_is_gateway_ready", side_effect=not_ready),
        mock.patch.object(runtime, "_start_server") as server_start,
        mock.patch("shibaclaw.desktop.runtime.subprocess.Popen", return_value=proc),
        mock.patch.dict(os.environ),
    ):
        worker = threading.Thread(target=start)
        worker.start()
        assert reached_health_check.wait(timeout=2)
        runtime.stop()
        worker.join(timeout=2)
        assert not worker.is_alive()
    proc.terminate.assert_called_once()
    server_start.assert_not_called()
    assert failures == ["Desktop startup was cancelled"]


def test_lightweight_preferences_read_does_not_load_providers(tmp_path):
    from shibaclaw.desktop import launcher

    config = tmp_path / "config.json"
    config.write_text('{"desktop":{"startHidden":true,"windowWidth":1111}}', encoding="utf-8")
    with mock.patch("shibaclaw.cli.base._make_provider") as provider:
        desktop = launcher._read_desktop_config(str(config))
    assert desktop.start_hidden is True
    assert desktop.window_width == 1111
    provider.assert_not_called()


def test_startup_html_has_no_network_or_file_asset_dependency(tmp_path):
    with mock.patch("shibaclaw.desktop.startup.get_assets_dir", return_value=tmp_path):
        page = startup_html()
    assert "Try again" in page
    assert "Open logs" in page
    assert "src=\"http" not in page
    assert "{{LOGO}}" not in page


def test_focus_restores_minimized_window_before_foreground():
    import ctypes

    from shibaclaw.desktop import launcher

    user32 = mock.Mock()
    user32.IsIconic.return_value = True
    window = mock.Mock()
    window.native = None
    with (
        mock.patch.object(launcher, "_resolve_windows_window_handle", return_value=1234),
        mock.patch.object(ctypes, "windll", types.SimpleNamespace(user32=user32), create=True),
    ):
        launcher._focus_windows_window(window)
    user32.ShowWindow.assert_called_once_with(1234, 9)
    user32.SetForegroundWindow.assert_called_once_with(1234)


def test_native_show_waits_off_ui_thread_and_contains_callback_errors():
    from shibaclaw.desktop import launcher

    shown = threading.Event()
    invoked = threading.Event()
    window = mock.Mock()
    window.events = types.SimpleNamespace(shown=shown)
    window.native.InvokeRequired = True
    window.show.side_effect = RuntimeError("Main window failed to start")

    def invoke(action):
        action()
        invoked.set()

    window.native.BeginInvoke.side_effect = invoke
    with mock.patch.dict(sys.modules, {"System": types.SimpleNamespace(Action=lambda action: action)}):
        launcher._window_show(window)
        window.native.BeginInvoke.assert_not_called()
        shown.set()
        assert invoked.wait(timeout=2)

    window.show.assert_called_once()


def test_single_instance_is_skipped_in_test_mode_and_non_windows():
    from shibaclaw.desktop import launcher

    with mock.patch.object(launcher, "get_os_type", return_value="windows"):
        assert launcher._single_instance_enabled() is False
    with mock.patch.object(launcher, "get_os_type", return_value="linux"):
        assert launcher._single_instance_enabled() is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows named kernel objects")
def test_windows_instance_queues_early_activation_and_releases_handles(tmp_path):
    from shibaclaw.desktop import single_instance

    owner = single_instance.WindowsDesktopInstance(tmp_path)
    duplicate = single_instance.WindowsDesktopInstance(tmp_path)
    replacement = single_instance.WindowsDesktopInstance(tmp_path)
    activated = threading.Event()
    try:
        assert owner.acquire_or_notify() is True
        with mock.patch.object(single_instance, "_allow_existing_window_foreground"):
            assert duplicate.acquire_or_notify() is False
        duplicate.close()
        # The signal survives the GUI not having registered its listener yet.
        owner.listen(activated.set)
        assert activated.wait(timeout=2)
        owner.close()
        assert replacement.acquire_or_notify() is True
    finally:
        duplicate.close()
        owner.close()
        replacement.close()


@pytest.mark.parametrize("kind", ["current", "legacy"])
def test_managed_autostart_migrates_only_the_known_enabled_command(tmp_path, kind):
    from shibaclaw.desktop import tray, windows_install

    root = tmp_path / "installed"
    data_root = tmp_path / "user-data"
    old = (
        root / "current" / "ShibaClaw.exe" if kind == "current"
        else data_root / "app" / "ShibaClaw" / "ShibaClaw.exe"
    )
    winreg = mock.Mock(KEY_QUERY_VALUE=1, KEY_SET_VALUE=2, REG_SZ=1)
    winreg.QueryValueEx.return_value = (f'"{old}"', 1)
    with (
        mock.patch.dict(sys.modules, {"winreg": winreg}),
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(windows_install, "get_managed_install_root", return_value=root),
        mock.patch.object(tray, "get_app_root", return_value=data_root),
    ):
        assert tray._migrate_managed_autostart() is True
    winreg.SetValueEx.assert_called_once_with(
        winreg.OpenKey.return_value, "ShibaClaw", 0, 1, f'"{root / "ShibaClaw.exe"}"'
    )
    winreg.CloseKey.assert_called_once()


@pytest.mark.parametrize("command", ["custom-wrapper.cmd", '"C:/other/current/ShibaClaw.exe"', "known-with-args"])
def test_managed_autostart_preserves_custom_commands(tmp_path, command):
    from shibaclaw.desktop import tray, windows_install

    if command == "known-with-args":
        command = f'"{tmp_path / "current" / "ShibaClaw.exe"}" --custom'
    winreg = mock.Mock(KEY_QUERY_VALUE=1, KEY_SET_VALUE=2, REG_SZ=1)
    winreg.QueryValueEx.return_value = (command, 1)
    with (
        mock.patch.dict(sys.modules, {"winreg": winreg}),
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(windows_install, "get_managed_install_root", return_value=tmp_path),
        mock.patch.object(tray, "get_app_root", return_value=tmp_path / "data"),
    ):
        assert tray._migrate_managed_autostart() is False
    winreg.SetValueEx.assert_not_called()


def test_managed_autostart_does_not_enable_a_missing_startup_entry(tmp_path):
    from shibaclaw.desktop import tray, windows_install

    winreg = mock.Mock(KEY_QUERY_VALUE=1, KEY_SET_VALUE=2, REG_SZ=1)
    winreg.QueryValueEx.side_effect = FileNotFoundError
    with (
        mock.patch.dict(sys.modules, {"winreg": winreg}),
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(windows_install, "get_managed_install_root", return_value=tmp_path),
    ):
        assert tray._migrate_managed_autostart() is False
    winreg.SetValueEx.assert_not_called()


def test_autostart_uses_stable_managed_launcher_and_preserves_fallbacks(tmp_path):
    from shibaclaw.desktop import tray, windows_install

    executable = tmp_path / "current" / "ShibaClaw.exe"
    with (
        mock.patch.object(windows_install, "get_managed_install_root", return_value=tmp_path),
        mock.patch.object(sys, "executable", str(executable)),
        mock.patch.object(sys, "frozen", True, create=True),
    ):
        assert tray._autostart_command() == f'"{tmp_path / "ShibaClaw.exe"}"'
    with (
        mock.patch.object(windows_install, "get_managed_install_root", return_value=None),
        mock.patch.object(sys, "executable", str(executable)),
        mock.patch.object(sys, "frozen", True, create=True),
    ):
        assert tray._autostart_command() == f'"{executable}"'
    with (
        mock.patch.object(windows_install, "get_managed_install_root", return_value=None),
        mock.patch.object(sys, "executable", str(tmp_path / "python.exe")),
        mock.patch.object(sys, "frozen", False, create=True),
    ):
        assert tray._autostart_command().endswith('" -m shibaclaw desktop')
