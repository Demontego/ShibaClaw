from typing import Any

from shibaclaw.agent.tools.secretary.send import BusinessSendTool


class _Sessions:
    def __init__(self, messages: list[dict[str, Any]]):
        self._session = type("Session", (), {"messages": messages})()

    def list_sessions(self) -> list[dict[str, str]]:
        return [{"key": "telegram:42"}]

    def get_or_create(self, key: str) -> Any:
        assert key == "telegram:42"
        return self._session


def test_business_send_requires_exact_peer_match():
    sessions = _Sessions(
        [
            {
                "role": "user",
                "metadata": {
                    "user_id": "42",
                    "username": "alice",
                    "first_name": "Alice",
                    "business_connection_id": "connection",
                },
            }
        ]
    )
    tool = BusinessSendTool(sessions)

    assert tool._matches("ali") == []
    assert [match[2] for match in tool._matches("alice")] == [42]
