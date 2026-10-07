"""Append-only turn journal.

A tool call is recorded before any I/O. The same id is never executed twice.
Input ids dedupe redelivery. Stop is ``hard`` or ``when_idle``.
``root is None`` keeps the journal in memory (incognito / ephemeral).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1
RESULT_CAP = 8000
REFUSAL = "Session journal cannot be resumed. This turn was not run."

_OPEN = {"ready", "awaiting", "canceling"}
_UNFINISHED = "This tool call did not finish. It was not started again."
_STOP_HARD = "Stopped. This tool was not started."
_STOP_IDLE = "Stopping when idle. This tool was not started."


class JournalError(Exception):
    """The journal cannot be trusted."""


class UnsupportedVersionError(JournalError):
    """A record version this process does not understand."""


class JournalCorruptError(JournalError):
    """A record could not be parsed. Fail closed."""


@dataclass(frozen=True)
class Claim:
    run: bool
    halt: bool = False
    result: str = ""


class TurnJournal:
    def __init__(self, root: Path | None) -> None:
        self.root = root
        self._memory: dict[str, list[dict[str, Any]]] = {}
        if root is not None:
            root.mkdir(parents=True, exist_ok=True)

    def accept_input(self, session_key: str, input_id: str | None) -> bool:
        """False when this input id was already accepted."""
        text = str(input_id or "").strip()
        if not text:
            return True
        if text in self._input_ids(session_key):
            return False
        self._append(session_key, {"kind": "input", "id": text})
        return True

    def claim(self, session_key: str, op_id: str, tool: str) -> Claim:
        """Record ``ready`` before the caller performs I/O."""
        mode = self.stop_mode(session_key)
        if mode == "hard":
            return Claim(False, True, _STOP_HARD)
        if mode == "when_idle":
            return Claim(False, True, _STOP_IDLE)
        op_id = str(op_id or tool)
        current = self._operations(session_key).get(op_id)
        if current is None:
            self._append(
                session_key,
                {
                    "kind": "operation",
                    "id": op_id,
                    "tool": tool,
                    "idempotency": op_id,
                    "status": "ready",
                },
            )
            return Claim(True)
        status = current["status"]
        if status in _OPEN:
            self.mark(session_key, op_id, "interrupted", _UNFINISHED)
            return Claim(False, False, _UNFINISHED)
        return Claim(False, False, current["result"] or _UNFINISHED)

    async def execute_claimed(
        self,
        session_key: str,
        op_id: str,
        tool: str,
        run: Callable[[], Awaitable[str]],
    ) -> tuple[str, bool]:
        claim = self.claim(session_key, op_id, tool)
        if not claim.run:
            return claim.result, claim.halt
        op_id = str(op_id or tool)
        self.mark(session_key, op_id, "awaiting")
        try:
            result = await run()
        except asyncio.CancelledError:
            self.mark(session_key, op_id, "canceled", "canceled")
            raise
        except JournalError:
            raise
        except Exception as exc:
            result = f"Error: Tool '{tool}' failed: {exc}"
            self.mark(session_key, op_id, "failed", result)
            return result, False
        if not isinstance(result, str):
            result = str(result)
        status = "failed" if result.startswith("Error") else "completed"
        self.mark(session_key, op_id, status, result)
        return result, False

    def mark(self, session_key: str, op_id: str, status: str, result: str = "") -> None:
        if len(result) <= RESULT_CAP:
            stored = result
        else:
            stored = result[:RESULT_CAP] + "\n...[journal truncated]"
        self._append(
            session_key,
            {"kind": "operation", "id": str(op_id), "status": status, "result": stored},
        )

    def note_truncation(self, session_key: str, source: str, reason: str) -> None:
        self._append(
            session_key,
            {"kind": "context", "change": "truncated", "source": source, "reason": reason},
        )

    def consume_interruptions(self, session_key: str) -> str | None:
        pending = [op for op in self._operations(session_key).values() if op["status"] in _OPEN]
        if not pending:
            return None
        lines = []
        for op in pending:
            self.mark(session_key, op["id"], "interrupted", _UNFINISHED)
            lines.append(f"- {op['tool'] or 'tool'} ({op['id']})")
        body = "\n".join(lines)
        return "[journal] These tool calls did not finish and were not started again:\n" + body

    def request_stop(self, session_key: str, mode: str) -> None:
        if mode not in {"hard", "when_idle"}:
            raise ValueError(mode)
        self._append(session_key, {"kind": "stop", "mode": mode})
        if mode != "hard":
            return
        for op in list(self._operations(session_key).values()):
            if op["status"] in _OPEN:
                self.mark(session_key, op["id"], "canceled", "canceled")

    def stop_mode(self, session_key: str) -> str | None:
        mode = ""
        for row in self._load(session_key):
            if row.get("kind") == "stop":
                mode = str(row.get("mode") or "")
        return mode or None

    def clear_stop(self, session_key: str) -> None:
        if self.stop_mode(session_key):
            self._append(session_key, {"kind": "stop", "mode": ""})

    def _operations(self, session_key: str) -> dict[str, dict[str, str]]:
        found: dict[str, dict[str, str]] = {}
        for row in self._load(session_key):
            if row.get("kind") != "operation":
                continue
            op_id = str(row.get("id") or "")
            if not op_id:
                continue
            current = found.setdefault(op_id, {"id": op_id, "tool": "", "status": "", "result": ""})
            if row.get("tool"):
                current["tool"] = str(row["tool"])
            if row.get("status"):
                current["status"] = str(row["status"])
            if row.get("result") is not None and "result" in row:
                current["result"] = str(row.get("result") or "")
        return found

    def _input_ids(self, session_key: str) -> set[str]:
        return {
            str(row["id"])
            for row in self._load(session_key)
            if row.get("kind") == "input" and row.get("id")
        }

    def _append(self, session_key: str, row: dict[str, Any]) -> None:
        record = {"v": FORMAT_VERSION, "session": session_key, **row}
        if self.root is None:
            self._memory.setdefault(session_key, []).append(record)
            return
        path = self._path(session_key)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _load(self, session_key: str) -> list[dict[str, Any]]:
        if self.root is None:
            return list(self._memory.get(session_key, []))
        path = self._path(session_key)
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise JournalCorruptError(f"{path.name}:{lineno}") from exc
            if not isinstance(row, dict) or row.get("v") != FORMAT_VERSION:
                raise UnsupportedVersionError(f"{path.name}:{lineno}")
            rows.append(row)
        return rows

    def _path(self, session_key: str) -> Path:
        assert self.root is not None
        digest = hashlib.sha256(session_key.encode()).hexdigest()
        return self.root / f"{digest}.jsonl"
