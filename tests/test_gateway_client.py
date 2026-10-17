import asyncio

import pytest
from unittest.mock import AsyncMock, patch
from shibaclaw.webui.gateway_client import GatewayClient, _http_get, _http_post, _http_delete


class MockStreamReader:
    def __init__(self, response_bytes: bytes):
        self.response_bytes = response_bytes
        self.read_count = 0

    async def read(self, limit: int = -1):
        if self.read_count > 0:
            return b""
        self.read_count += 1
        return self.response_bytes


class MockStreamWriter:
    def __init__(self):
        self.written_data = b""
        self.is_closed = False

    def write(self, data: bytes):
        self.written_data += data

    async def drain(self):
        pass

    def close(self):
        self.is_closed = True

    async def wait_closed(self):
        pass


@pytest.mark.asyncio
async def test_http_get_success():
    resp = b"HTTP/1.1 200 OK\r\n\r\n{\"result\": \"success\"}"
    reader = MockStreamReader(resp)
    writer = MockStreamWriter()

    with patch("asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
        res = await _http_get(["localhost"], 8000, "/api/test", "token123")
        assert res == {"result": "success"}
        assert b"GET /api/test HTTP/1.0" in writer.written_data
        assert b"Authorization: Bearer token123" in writer.written_data


@pytest.mark.asyncio
async def test_http_get_fail_status_body_200():
    resp = b"HTTP/1.1 500 Internal Server Error\r\n\r\n{\"code\": 200, \"msg\": \"fake 200\"}"
    reader = MockStreamReader(resp)
    writer = MockStreamWriter()

    with patch("asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
        res = await _http_get(["localhost"], 8000, "/api/test", "token123")
        assert res is None


@pytest.mark.asyncio
async def test_http_post_success():
    resp = b"HTTP/1.1 200 OK\r\n\r\n{\"status\": \"created\"}"
    reader = MockStreamReader(resp)
    writer = MockStreamWriter()

    with patch("asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
        res = await _http_post(["localhost"], 8000, "/api/test", {"data": "val"}, "token123")
        assert res == {"status": "created"}
        assert b"POST /api/test HTTP/1.0" in writer.written_data
        assert b"{\"data\": \"val\"}" in writer.written_data


@pytest.mark.asyncio
async def test_http_post_fail_status_body_200():
    resp = b"HTTP/1.1 400 Bad Request\r\n\r\n{\"err\": 200}"
    reader = MockStreamReader(resp)
    writer = MockStreamWriter()

    with patch("asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
        res = await _http_post(["localhost"], 8000, "/api/test", {"data": "val"}, "token123")
        assert res is None


@pytest.mark.asyncio
async def test_http_delete_success():
    resp = b"HTTP/1.1 200 OK\r\n\r\n{\"deleted\": true}"
    reader = MockStreamReader(resp)
    writer = MockStreamWriter()

    with patch("asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
        res = await _http_delete(["localhost"], 8000, "/api/test", "token123")
        assert res == {"deleted": True}
        assert b"DELETE /api/test HTTP/1.0" in writer.written_data


@pytest.mark.asyncio
async def test_http_delete_fail_status_body_200():
    resp = b"HTTP/1.1 403 Forbidden\r\n\r\n{\"reason\": \"no permission 200\"}"
    reader = MockStreamReader(resp)
    writer = MockStreamWriter()

    with patch("asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
        res = await _http_delete(["localhost"], 8000, "/api/test", "token123")
        assert res is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            b'HTTP/1.1 401 Unauthorized\r\nContent-Type: application/json\r\n\r\n{"error":"unauthorized"}',
            {"t": "e", "error": "Gateway HTTP 401: unauthorized"},
        ),
        (
            b'HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\n\r\n{"error":"no_provider"}',
            {"t": "e", "error": "Gateway HTTP 503: no_provider"},
        ),
        (
            b'HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\n\r\n',
            {"t": "e", "error": "Gateway chat stream ended without a response"},
        ),
    ],
)
async def test_http_chat_stream_reports_gateway_failure(response, expected):
    reader = asyncio.StreamReader()
    reader.feed_data(response)
    reader.feed_eof()
    writer = MockStreamWriter()
    client = GatewayClient()
    with patch("shibaclaw.webui.utils._resolve_gateway_hosts", return_value=(["localhost"], 8000)), \
         patch("asyncio.open_connection", AsyncMock(return_value=(reader, writer))):
        events = [event async for event in client._http_chat_stream_fallback({"content": "hello"})]
    assert events == [expected]
    assert b"POST /api/chat HTTP/1.0" in writer.written_data
    assert writer.is_closed


@pytest.mark.asyncio
async def test_http_chat_stream_keeps_successful_response():
    reader = asyncio.StreamReader()
    reader.feed_data(
        b'HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\n\r\n'
        b'{"t":"rt","c":"Hello"}\n{"t":"r","content":"Hello","media":[]}\n'
    )
    reader.feed_eof()
    client = GatewayClient()
    with patch("shibaclaw.webui.utils._resolve_gateway_hosts", return_value=(["localhost"], 8000)), \
         patch("asyncio.open_connection", AsyncMock(return_value=(reader, MockStreamWriter()))):
        events = [event async for event in client._http_chat_stream_fallback({"content": "hello"})]
    assert events == [
        {"t": "rt", "c": "Hello"},
        {"t": "r", "content": "Hello", "media": []},
    ]
