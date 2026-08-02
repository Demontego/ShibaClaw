from shibaclaw.agent.tools.secretary.preamble import (
    build_guest_preamble,
    build_secretary_preamble,
)


class _Sessions:
    def get_or_create(self, key):
        del key
        return type("Session", (), {"messages": []})()


def test_guest_preamble_uses_configured_owner_ids():
    preamble = build_guest_preamble(
        _Sessions(), chat_id="10", meta={"user_id": "1", "first_name": "Owner"}, owner_ids={"1"}
    )

    assert "This speaker is the owner." in preamble
    assert "Allowed tools only" not in preamble


def test_guest_preamble_does_not_treat_star_as_owner():
    preamble = build_guest_preamble(
        _Sessions(), chat_id="10", meta={"user_id": "1", "first_name": "Peer"}, owner_ids={"*"}
    )

    assert "This speaker is not the owner." in preamble
    assert "web_search and web_fetch" in preamble
    assert "business_search" in preamble


def test_secretary_preamble_limits_peer_to_current_dm():
    preamble = build_secretary_preamble(
        _Sessions(), chat_id="10", meta={"user_id": "2", "first_name": "Peer"}, owner_ids={"1"}
    )

    assert "Use only this-DM context." in preamble
    assert "Refuse business_search, business_send" in preamble
