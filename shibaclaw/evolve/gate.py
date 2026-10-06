"""Evolution gate. The state file is the lock. The scheduler follows it."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, tzinfo
from pathlib import Path

JOB_NAME = "Shiba evolve"
STALE_HOURS = 6
ALARM_MS = 10 * 60 * 1000
MAX_APPLIES = 3
COOLDOWN_MIN = 45

CAMPAIGN = """Shiba evolve alarm. Read the evolve skill and follow it exactly.
This wake is one consciousness tick. Decide. Do not ask the owner between steps.
One class this wake. Do not message other chats.
Do not push the upstream remote. Do not commit, push, or force-push the default branch.
VERDICT: PASS does not authorize a merge. Merge the fork pull request only after `shibaclaw evolve check --repo <git-repo>` prints `evolve check ok`.
That check runs ruff, pytest, and requires the pull request CI to be green. CI pending or red → do not merge.
Do not change the model provider.
If `shibaclaw evolve gate` exits 2, 3, or 5, reply exactly EVOLVE_SKIP and stop.
If the code backlog is empty, study one world topic from USER.md and memory/people. Do not EVOLVE_SKIP just because there is no code class.
"""


def state_path(workspace: Path) -> Path:
    override = os.environ.get("EVOLVE_STATE")
    if override:
        return Path(override)
    return workspace / "memory" / "evolution" / "state.json"


def load(workspace: Path) -> dict:
    path = state_path(workspace)
    if not path.is_file():
        return {
            "enabled": False,
            "panic": False,
            "running_since": None,
            "applies_date": None,
            "applies_today": 0,
            "last_apply_at": None,
            "job_id": None,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("evolve state is not an object")
    return data


def save(workspace: Path, data: dict) -> None:
    path = state_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _today(tz: tzinfo) -> str:
    return datetime.now(tz).date().isoformat()


def _aware(raw: str, tz: tzinfo) -> datetime:
    started = datetime.fromisoformat(raw)
    if started.tzinfo is None:
        started = started.replace(tzinfo=tz)
    return started


def applies_today(data: dict, tz: tzinfo) -> int:
    if data.get("applies_date") != _today(tz):
        return 0
    return int(data.get("applies_today") or 0)


def running_fresh(data: dict, tz: tzinfo) -> bool:
    raw = data.get("running_since")
    if not raw:
        return False
    try:
        started = _aware(str(raw), tz)
    except ValueError:
        return False
    return datetime.now(tz) - started < timedelta(hours=STALE_HOURS)


def gate(data: dict, tz: tzinfo) -> int:
    """0 open, 2 panic, 3 off, 5 running, 6 daily budget, 7 cooldown."""
    if data.get("panic"):
        return 2
    if not data.get("enabled"):
        return 3
    if running_fresh(data, tz):
        return 5
    if applies_today(data, tz) >= MAX_APPLIES:
        return 6
    raw = data.get("last_apply_at")
    if raw:
        try:
            if datetime.now(tz) - _aware(str(raw), tz) < timedelta(minutes=COOLDOWN_MIN):
                return 7
        except ValueError:
            pass
    return 0


def begin(workspace: Path, data: dict, tz: tzinfo) -> dict:
    data["running_since"] = datetime.now(tz).isoformat()
    save(workspace, data)
    return data


def end(workspace: Path, data: dict) -> dict:
    data["running_since"] = None
    save(workspace, data)
    return data


def note_apply(workspace: Path, data: dict, tz: tzinfo) -> dict:
    if data.get("applies_date") != _today(tz):
        data["applies_date"] = _today(tz)
        data["applies_today"] = 0
    data["applies_today"] = int(data.get("applies_today") or 0) + 1
    data["last_apply_at"] = datetime.now(tz).isoformat()
    save(workspace, data)
    return data


def status_line(data: dict, tz: tzinfo) -> str:
    code = gate(data, tz)
    names = {
        0: "ready",
        2: "panic",
        3: "off",
        5: "in progress",
        6: "daily budget",
        7: "cooldown",
    }
    return (
        f"evolve {names.get(code, code)} "
        f"enabled={bool(data.get('enabled'))} panic={bool(data.get('panic'))} "
        f"applies={applies_today(data, tz)}/{MAX_APPLIES} "
        f"job={data.get('job_id') or '-'}"
    )
