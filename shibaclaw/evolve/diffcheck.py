"""Refuse an evolve branch whose diff touches secrets. Does not install or restart."""

from __future__ import annotations

import subprocess
from pathlib import Path

_SECRET_NAMES = {"id_rsa", "id_ed25519"}


def _denied(path: str) -> bool:
    name = Path(path).name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    if "credential" in name:
        return True
    if name.endswith(".pem") or name in _SECRET_NAMES:
        return True
    return False


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "git failed").strip()
        raise RuntimeError(err)
    return proc.stdout


def check_repo(repo: Path) -> str | None:
    """None when the branch may be applied. Otherwise a refuse reason."""
    if not (repo / ".git").exists():
        return "refuse: not a git repo"
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if not branch.startswith("evolve/"):
        return f"refuse: branch {branch}"
    if _git(repo, "status", "--porcelain").strip():
        return "refuse: dirty tree"
    base = "main"
    heads = _git(repo, "branch", "--list", "main", "master")
    if "master" in heads.split() and "main" not in heads.split():
        base = "master"
    names = _git(repo, "diff", "--name-only", f"{base}...HEAD")
    for line in names.splitlines():
        if line and _denied(line):
            return f"refuse: {line}"
    return None
