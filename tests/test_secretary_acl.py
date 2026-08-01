import pytest

from shibaclaw.agent.tools.secretary.acl import resolve_secretary_access


@pytest.mark.parametrize(
    ("channel", "meta"),
    [
        ("telegram", {"is_guest": True, "user_id": "42"}),
        ("telegram", {"user_id": "42"}),
        ("telegram", {"user_id": "42", "secretary_summon": True}),
    ],
)
def test_secretary_acl_denies_non_owners(channel, meta):
    access, reason = resolve_secretary_access(channel, "42", meta, {"1"})

    assert access == "deny"
    assert reason


@pytest.mark.parametrize("owner_id", ["1", "1|owner_username"])
def test_secretary_acl_allows_configured_owner_ids(owner_id):
    access, detail = resolve_secretary_access("telegram", "1", {"user_id": "1"}, {owner_id})

    assert (access, detail) == ("full", None)


@pytest.mark.parametrize("channel", ["webui", "cli", "automation"])
def test_secretary_acl_allows_owner_operated_channels(channel):
    assert resolve_secretary_access(channel, "42", {"is_guest": False}) == ("full", None)


def test_secretary_acl_never_treats_star_as_owner():
    access, reason = resolve_secretary_access("telegram", "42", {"user_id": "42"}, {"*"})

    assert access == "deny"
    assert reason
