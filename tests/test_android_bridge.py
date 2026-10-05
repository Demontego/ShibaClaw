"""WebUI Android bridge helpers."""

from shibaclaw.webui.android_bridge import parse_digest_text, session_key_for


def test_android_session_key():
    assert session_key_for("pixel.1") == "android:pixel.1"


def test_parse_digest_plain_json():
    raw = (
        '{"mood":"IDLE","mood_line":"Ears up.",'
        '"fact":"Shibas are cats in dog suits.",'
        '"news":["Markets calm","New comet spotted"]}'
    )
    d = parse_digest_text(raw)
    assert d is not None
    assert d.mood == "IDLE"
    assert d.mood_line == "Ears up."
    assert len(d.news) == 2


def test_parse_digest_fenced():
    raw = """Here you go:
```json
{"mood":"ALERT","mood_line":"Woof!", "fact":"Fact", "news":["A"]}
```
"""
    d = parse_digest_text(raw)
    assert d is not None
    assert d.mood == "ALERT"
    assert d.news == ["A"]


def test_parse_digest_malformed():
    assert parse_digest_text("") is None
    assert parse_digest_text("not json") is None
    assert parse_digest_text('{"mood":1,"news":"x"}') is None
