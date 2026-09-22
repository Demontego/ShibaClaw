"""Read-only picture of self-evolution for the WebUI."""

from __future__ import annotations

import json
import subprocess
from datetime import timezone, tzinfo
from pathlib import Path

from shibaclaw.evolve.gate import JOB_NAME, MAX_APPLIES, applies_today, gate, load

UTC = timezone.utc
_TEXT_CAP = 12000


def _tail(path: Path, limit: int = _TEXT_CAP) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= limit:
        return text
    return text[-limit:]


def _body_repo(workspace: Path) -> Path | None:
    root = workspace / "repositories"
    if not root.is_dir():
        return None
    preferred = root / "ShibaClaw"
    if (preferred / ".git").exists():
        return preferred
    repos = [p for p in root.iterdir() if p.is_dir() and (p / ".git").exists()]
    if len(repos) == 1:
        return repos[0]
    return None


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout


def _repo_view(repo: Path) -> dict:
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    dirty = bool(_git(repo, "status", "--porcelain").strip())
    commits = []
    for line in _git(repo, "log", "-12", "--pretty=format:%h%x09%ci%x09%s").splitlines():
        sha, date, subject = (line.split("\t", 2) + ["", ""])[:3]
        if sha:
            commits.append({"sha": sha, "date": date, "subject": subject})
    branches = [
        line
        for line in _git(
            repo,
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname:short)",
            "refs/heads/evolve",
        ).splitlines()
        if line
    ]
    return {
        "name": repo.name,
        "branch": branch,
        "dirty": dirty,
        "commits": commits,
        "evolve_branches": branches,
    }


def _job(path: Path | None) -> dict | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        return None
    job = next((item for item in jobs if item.get("name") == JOB_NAME), None)
    if not isinstance(job, dict):
        return None
    schedule = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}
    state = job.get("state") if isinstance(job.get("state"), dict) else {}
    return {
        "enabled": bool(job.get("enabled")),
        "every_ms": schedule.get("everyMs") or schedule.get("every_ms"),
        "next_run_at_ms": state.get("nextRunAtMs") or state.get("next_run_at_ms") or 0,
        "last_status": state.get("lastStatus") or state.get("last_status") or "",
        "last_run_at_ms": state.get("lastRunAtMs") or state.get("last_run_at_ms") or 0,
    }


def _body(workspace: Path) -> dict | None:
    path = workspace / "memory" / "evolution" / "body.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {"sha": str(data.get("sha") or ""), "at": str(data.get("at") or "")}


def snapshot(
    workspace: Path,
    automation_file: Path | None = None,
    tz: tzinfo | None = None,
) -> dict:
    zone = tz or UTC
    data = load(workspace)
    code = gate(data, zone)
    names = {0: "ready", 2: "panic", 3: "off", 5: "in progress", 6: "daily budget", 7: "cooldown"}
    repo = _body_repo(workspace)
    knowledge = workspace / "memory" / "knowledge"
    return {
        "label": names.get(code, str(code)),
        "code": code,
        "enabled": bool(data.get("enabled")),
        "panic": bool(data.get("panic")),
        "applies": applies_today(data, zone),
        "max_applies": MAX_APPLIES,
        "running_since": data.get("running_since"),
        "job": _job(automation_file),
        "body": _body(workspace),
        "chronicle": _tail(workspace / "memory" / "evolution" / "LOG.md"),
        "backlog": _tail(knowledge / "improvement-backlog.md"),
        "patterns": _tail(knowledge / "patterns.md"),
        "world": _tail(workspace / "memory" / "evolution" / "WORLD.md"),
        "repo": _repo_view(repo) if repo else None,
    }
