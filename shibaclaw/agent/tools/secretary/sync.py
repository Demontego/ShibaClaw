"""Export Chat Automation sessions to markdown and search them with qmd."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

COLLECTION = "secretary"


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        )
    return ""


def _meta(message: dict[str, Any]) -> dict[str, Any]:
    metadata = message.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _session_peer_id(key: str) -> int | None:
    parts = key.split(":")
    return int(parts[1]) if len(parts) >= 2 and parts[1].lstrip("-").isdigit() else None


def _is_business(messages: list[dict[str, Any]]) -> bool:
    return any(_meta(message).get("business_connection_id") for message in messages)


def _is_bot_peer(messages: list[dict[str, Any]], peer_id: int | None) -> bool:
    return any(
        _meta(message).get("is_bot_sender")
        and peer_id is not None
        and str(_meta(message).get("user_id")) == str(peer_id)
        for message in messages
    )


def _peer_info(messages: list[dict[str, Any]], peer_id: int | None) -> tuple[str, str | None]:
    for message in reversed(messages):
        metadata = _meta(message)
        if message.get("role") != "user" or (
            peer_id is not None and str(metadata.get("user_id")) != str(peer_id)
        ):
            continue
        name = metadata.get("first_name") or metadata.get("username") or str(peer_id or "peer")
        username = metadata.get("username")
        return str(name), str(username) if username else None
    return str(peer_id or "peer"), None


def _safe_filename(peer_id: int | None, name: str) -> str:
    slug = re.sub(r"[^\w-]+", "_", name, flags=re.UNICODE).strip("_")[:40] or "peer"
    return f"{peer_id or 0}_{slug}.md"


def _load_jsonl(path: Path) -> tuple[str, list[dict[str, Any]]]:
    key = path.stem.replace("_", ":", 1)
    messages: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if data.get("_type") == "metadata":
            key = str(data.get("key") or key)
        else:
            messages.append(data)
    return key, messages


def _render_md(
    key: str, peer_id: int | None, name: str, username: str | None, messages: list[dict[str, Any]]
) -> str:
    lines = [
        "---",
        f"peer_id: {peer_id or ''}",
        f"peer_name: {name}",
        f"username: {username or ''}",
        f"session_key: {key}",
        "source: telegram_chat_automation",
        "---",
        "",
        f"# Chat with {name}",
        "",
    ]
    for message in messages:
        metadata = _meta(message)
        text = _content_text(message.get("content")).strip()
        if (
            message.get("role") != "user"
            or message.get("tool_calls")
            or not metadata.get("business_connection_id")
            or not text
        ):
            continue
        timestamp = str(message.get("timestamp") or "?")
        timestamp = timestamp[:16].replace("T", " ")
        speaker = name if str(metadata.get("user_id")) == str(peer_id) else "owner"
        lines.extend((f"## {timestamp} {speaker}", text, ""))
    return "\n".join(lines).rstrip() + "\n"


def secretary_dir(workspace: Path) -> Path:
    return workspace / "memory" / "secretary"


def sync_secretary_markdown(workspace: Path) -> dict[str, Any]:
    """Rewrite the secretary markdown projection from Telegram session JSONL."""
    out_dir = secretary_dir(workspace)
    out_dir.mkdir(parents=True, exist_ok=True)
    active_files: set[str] = set()
    written = skipped_bot = 0
    for path in sorted((workspace / "sessions").glob("telegram_*.jsonl")):
        try:
            key, messages = _load_jsonl(path)
        except (OSError, json.JSONDecodeError):
            continue
        if not key.startswith("telegram:") or not _is_business(messages):
            continue
        peer_id = _session_peer_id(key)
        if _is_bot_peer(messages, peer_id):
            skipped_bot += 1
            continue
        name, username = _peer_info(messages, peer_id)
        body = _render_md(key, peer_id, name, username, messages)
        if "\n## " not in body:
            continue
        destination = out_dir / _safe_filename(peer_id, name)
        active_files.add(destination.name)
        if not destination.exists() or destination.read_text(encoding="utf-8") != body:
            destination.write_text(body, encoding="utf-8")
            written += 1
    removed = 0
    for stale in out_dir.glob("*.md"):
        if stale.name not in active_files:
            stale.unlink()
            removed += 1
    return {"dir": str(out_dir), "files": len(active_files), "written": written,
            "removed": removed, "skipped_bot": skipped_bot}


def _qmd_env() -> dict[str, str]:
    env = os.environ.copy()
    home = Path.home()
    extras = (home / ".bun" / "bin", home / ".local" / "bin")
    env["PATH"] = ":".join(str(path) for path in extras if path.is_dir()) + ":" + env.get("PATH", "")
    return env


def _qmd(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, env=_qmd_env(), timeout=timeout, check=False)


def ensure_qmd_collection(workspace: Path) -> str | None:
    out_dir = secretary_dir(workspace)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        listed = _qmd(["qmd", "collection", "list"], 60)
    except FileNotFoundError:
        return "qmd CLI not found (install @tobilu/qmd + bun)"
    if listed.returncode:
        return f"qmd collection list failed: {listed.stderr.strip() or listed.stdout.strip()}"
    if re.search(r"(?m)^\s*secretary\b", listed.stdout) or "secretary (" in listed.stdout:
        return None
    added = _qmd(
        ["qmd", "collection", "add", str(out_dir), "--name", COLLECTION, "--mask", "**/*.md"], 120
    )
    return None if not added.returncode else f"qmd collection add failed: {added.stderr.strip() or added.stdout.strip()}"


def qmd_reindex(*, embed: bool = False) -> str | None:
    try:
        update = _qmd(["qmd", "update"], 300)
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return f"qmd update failed: {error}"
    if update.returncode:
        return f"qmd update failed: {update.stderr.strip() or update.stdout.strip()}"
    if embed:
        embedded = _qmd(["qmd", "embed"], 1800)
        if embedded.returncode:
            return f"qmd embed failed: {embedded.stderr.strip() or embedded.stdout.strip()}"
    return None


def qmd_search(query: str, *, top_k: int = 20, collection: str = COLLECTION) -> tuple[str | None, list[dict[str, Any]]]:
    try:
        result = _qmd(
            ["qmd", "search", query, "-c", collection, "--json", "-n", str(max(1, min(40, top_k)))], 120
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return str(error), []
    if result.returncode:
        return result.stderr.strip() or result.stdout.strip() or "qmd search failed", []
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        return "qmd search returned non-JSON", []
    results = data.get("results", []) if isinstance(data, dict) else data
    return (None, [item for item in results if isinstance(item, dict)]) if isinstance(results, list) else ("unexpected qmd JSON shape", [])


def format_qmd_hits(results: list[dict[str, Any]], query: str, *, peer: str | None = None) -> str:
    peer_filter = (peer or "").casefold()
    hits: list[str] = []
    for result in results:
        path = str(result.get("file") or result.get("path") or result.get("filepath") or "")
        snippet = re.sub(r"\s+", " ", str(result.get("snippet") or result.get("text") or "")).strip()
        if peer_filter and peer_filter not in f"{path} {snippet}".casefold():
            continue
        score = result.get("score")
        score_text = f"{float(score):.3f}" if isinstance(score, (int, float)) else "?"
        hits.append(f"- [{score_text}] {Path(path).stem or '?'}: {snippet[:220]}{'…' if len(snippet) > 220 else ''}")
    return "\n".join([f"Secretary archive (qmd) — {len(hits)} hits for {query!r}:", *hits]) if hits else f"No qmd hits for {query!r}."
