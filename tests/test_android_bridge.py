"""WebUI Android session key helper."""

from shibaclaw.webui.android_bridge import session_key_for


def test_android_session_key():
    assert session_key_for("pixel.1") == "android:pixel.1"
