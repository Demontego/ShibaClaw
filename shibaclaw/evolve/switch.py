"""Owner switch. Arms the live AutomationService when one is passed in."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from shibaclaw.automation.types import AutomationPayload, AutomationSchedule
from shibaclaw.evolve.gate import (
    ALARM_MS,
    CAMPAIGN,
    JOB_NAME,
    begin,
    end,
    gate,
    load,
    note_apply,
    save,
    status_line,
)

UTC = ZoneInfo("UTC")


def owner_chat(channels_config: Any | None) -> str | None:
    """First numeric allowFrom id. `*` is not an owner."""
    if channels_config is None:
        return None
    if isinstance(channels_config, dict):
        tg = channels_config.get("telegram")
    else:
        extra = getattr(channels_config, "model_extra", None) or {}
        tg = extra.get("telegram") if isinstance(extra, dict) else None
        if tg is None:
            tg = getattr(channels_config, "telegram", None)
    if tg is None:
        return None
    if hasattr(tg, "model_dump"):
        data = tg.model_dump(by_alias=True)
    elif isinstance(tg, dict):
        data = tg
    else:
        return None
    raw = data.get("allowFrom") or data.get("allow_from") or []
    if not isinstance(raw, list):
        return None
    for item in raw:
        text = str(item).strip() if item is not None else ""
        if text and text != "*" and text.lstrip("-").isdigit():
            return text
    return None


def is_owner_surface(
    channel: str,
    sender_id: str,
    metadata: dict | None,
    owner_ids: set[str],
) -> bool:
    meta = metadata or {}
    if meta.get("is_group") or meta.get("business_connection_id") or meta.get("is_guest"):
        return False
    ch = (channel or "").lower()
    if ch in {"webui", "cli"}:
        return True
    if ch == "telegram":
        return str(sender_id) in owner_ids
    return False


def _payload(owner: str | None) -> dict:
    return {
        "kind": "scheduled",
        "message": CAMPAIGN,
        "deliver": bool(owner),
        "channel": "telegram" if owner else None,
        "to": owner,
        "sessionKey": "automation:shiba-evolve",
        "targets": {"telegram": owner} if owner else {},
    }


def _schedule(every_ms: int) -> dict:
    return {"kind": "every", "everyMs": every_ms, "expr": None, "tz": None}


def sync_alarm(
    automation: Any,
    data: dict,
    *,
    enabled: bool,
    owner: str | None,
    every_ms: int = ALARM_MS,
) -> str:
    found = next((job for job in automation.list_jobs() if job.name == JOB_NAME), None)
    if found is None:
        found = automation.add_job(
            name=JOB_NAME,
            schedule=AutomationSchedule(kind="every", every_ms=every_ms),
            payload=AutomationPayload(
                kind="scheduled",
                message=CAMPAIGN,
                deliver=bool(owner),
                channel="telegram" if owner else None,
                to=owner,
                session_key="automation:shiba-evolve",
                targets={"telegram": owner} if owner else {},
            ),
        )
    updated = automation.update_job(
        found.id,
        {"enabled": enabled, "schedule": _schedule(every_ms), "payload": _payload(owner)},
    )
    job_id = updated.id if updated is not None else found.id
    data["job_id"] = job_id
    return f"job {job_id} enabled={enabled} alarm={every_ms // 60000}m"


def handle(
    action: str,
    *,
    workspace: Path,
    automation: Any | None = None,
    owner: str | None = None,
    tz: ZoneInfo | None = None,
    repo: Path | None = None,
) -> tuple[str, int]:
    zone = tz or UTC
    data = load(workspace)
    if action == "status":
        return status_line(data, zone), 0
    if action == "on":
        data["enabled"] = True
        data["panic"] = False
        save(workspace, data)
        armed = _arm(automation, data, workspace, enabled=True, owner=owner)
        return f"evolve on. Alarm every 30 min. Report only to the owner. {armed}", 0
    if action == "off":
        data["enabled"] = False
        data["running_since"] = None
        save(workspace, data)
        armed = _arm(automation, data, workspace, enabled=False, owner=owner)
        return f"evolve off. {armed}", 0
    if action == "panic":
        data["panic"] = True
        data["enabled"] = False
        data["running_since"] = None
        save(workspace, data)
        armed = _arm(automation, data, workspace, enabled=False, owner=owner)
        return f"panic. No restart. {armed}", 0
    if action == "gate":
        code = gate(data, zone)
        if code == 0:
            begin(workspace, data, zone)
            return "gate open", 0
        return status_line(data, zone), code
    if action == "end":
        end(workspace, data)
        return "evolve end", 0
    if action == "note-apply":
        note_apply(workspace, data, zone)
        return status_line(load(workspace), zone), 0
    if action == "check":
        from shibaclaw.evolve.diffcheck import check_repo

        if repo is None:
            return "evolve check needs --repo", 64
        reason = check_repo(repo)
        if reason:
            return reason, 1
        return "evolve check ok", 0
    return "usage: evolve on|off|status|panic|gate|end|note-apply|check", 64


def _arm(
    automation: Any | None,
    data: dict,
    workspace: Path,
    *,
    enabled: bool,
    owner: str | None,
) -> str:
    if automation is None:
        save(workspace, data)
        return "alarm not armed"
    try:
        text = sync_alarm(automation, data, enabled=enabled, owner=owner)
    except Exception as exc:
        save(workspace, data)
        return f"alarm not armed ({exc.__class__.__name__})"
    save(workspace, data)
    return text
