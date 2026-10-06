"""Refuse an evolve merge until local tests and the fork PR CI match the workflow."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

_OK = {"SUCCESS", "SKIPPED", "NEUTRAL"}
_PENDING = {"QUEUED", "IN_PROGRESS", "PENDING", "REQUESTED", "WAITING", "EXPECTED"}

LOCAL_CI = (
    ["uv", "run", "ruff", "check", "."],
    ["uv", "run", "pytest", "tests/", "-q"],
)


def run_local_ci(repo: Path) -> str | None:
    """None when ruff and pytest pass. Same commands as the Linux CI job."""
    for cmd in LOCAL_CI:
        proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            blob = f"{proc.stdout or ''}\n{proc.stderr or ''}".strip()
            last = blob.splitlines()[-1] if blob else "failed"
            return f"refuse: {' '.join(cmd)}: {last}"
    return None


def _rollup_reason(rollup: list) -> str | None:
    if not rollup:
        return "refuse: CI pending"
    pending: list[str] = []
    bad: list[str] = []
    for item in rollup:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("context") or "check")
        status = str(item.get("status") or "").upper()
        conclusion = str(item.get("conclusion") or item.get("state") or "").upper()
        if status in _PENDING or conclusion in _PENDING:
            pending.append(name)
            continue
        if conclusion not in _OK:
            bad.append(f"{name} {conclusion or 'missing'}")
    if pending:
        return "refuse: CI pending " + ", ".join(pending)
    if bad:
        return "refuse: CI " + ", ".join(bad)
    return None


def github_ci(repo: Path) -> str | None:
    """None when the open fork PR has finished green checks."""
    proc = subprocess.run(
        ["gh", "pr", "view", "--json", "state,statusCheckRollup"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "no pull request").strip()
        line = err.splitlines()[-1] if err else "no pull request"
        return f"refuse: {line}"
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return "refuse: bad gh pr json"
    state = str(data.get("state") or "")
    if state != "OPEN":
        return f"refuse: pull request {state or 'missing'}"
    rollup = data.get("statusCheckRollup") or []
    if not isinstance(rollup, list):
        return "refuse: CI pending"
    return _rollup_reason(rollup)
