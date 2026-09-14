"""Characterization: gateway WS/HTTP action surface used by WebUI."""

from __future__ import annotations

import ast
from pathlib import Path


GATEWAY_PATH = Path(__file__).resolve().parents[1] / "shibaclaw" / "cli" / "gateway.py"


def _string_compares_to_action(tree: ast.AST) -> set[str]:
    actions: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "action":
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                    actions.add(comparator.value)
    return actions


def test_gateway_ws_exposes_core_chat_and_automation_actions():
    tree = ast.parse(GATEWAY_PATH.read_text(encoding="utf-8"))
    actions = _string_compares_to_action(tree)
    required = {
        "status",
        "chat",
        "cancel",
        "steer",
        "restart",
        "reload",
        "automation.list",
        "automation.trigger",
        "automation.status",
        "automation.enable",
        "automation.remove",
        "automation.create",
        "automation.get",
        "automation.update",
    }
    missing = required - actions
    assert not missing, f"missing gateway actions: {sorted(missing)}"


def test_gateway_legacy_cron_heartbeat_aliases_removed():
    tree = ast.parse(GATEWAY_PATH.read_text(encoding="utf-8"))
    actions = _string_compares_to_action(tree)
    legacy = {"cron.list", "cron.trigger", "heartbeat.status", "heartbeat.trigger"}
    assert not (legacy & actions)
