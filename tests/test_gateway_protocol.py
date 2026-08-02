"""Tests for gateway protocol helpers (token coalesce, job serialize)."""

from __future__ import annotations

import pytest

from shibaclaw.cli.gateway_protocol import TokenCoalescer, serialize_automation_job


@pytest.mark.asyncio
async def test_token_coalescer_batches_and_flushes_final():
    sent: list[str] = []

    async def send(chunk: str) -> None:
        sent.append(chunk)

    coalescer = TokenCoalescer(send, interval_s=0.2, max_chars=10)
    await coalescer.add("hello")
    await coalescer.add(" ")
    await coalescer.add("world!!")  # crosses max_chars with buffer
    await coalescer.close()

    assert "".join(sent) == "hello world!!"
    assert coalescer.token_count == 3
    assert coalescer.send_count >= 1
    assert coalescer.send_count < coalescer.token_count


def test_serialize_automation_job_shape():
    class _Sched:
        kind = "every"
        at_ms = None
        every_ms = 60000
        expr = None
        tz = "UTC"

    class _Payload:
        kind = "scheduled"
        message = "hi"
        heartbeat_file = None
        deliver = False
        channel = "telegram"
        to = "1"
        targets = None

    class _State:
        next_run_at_ms = 1
        last_run_at_ms = None
        last_status = "ok"
        last_error = None
        run_count = 2

    class _Job:
        id = "j1"
        name = "n"
        enabled = True
        schedule = _Sched()
        payload = _Payload()
        state = _State()
        delete_after_run = False

    data = serialize_automation_job(_Job())
    assert data["id"] == "j1"
    assert data["payload"]["message"] == "hi"
    assert data["schedule"]["everyMs"] == 60000
