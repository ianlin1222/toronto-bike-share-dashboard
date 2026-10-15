from __future__ import annotations

import json

import httpx
import pytest

from bikeshare.gbfs.client import FeedFetchError, GBFSClient


def test_bounded_retry_recovers_from_rate_limit_and_server_failure() -> None:
    statuses = iter([429, 503, 200])
    calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        status = next(statuses)
        return httpx.Response(
            status,
            request=request,
            headers={"Retry-After": "0"} if status == 429 else {},
            content=(
                json.dumps({"last_updated": 0, "ttl": 10, "data": {"stations": []}})
                if status == 200
                else "temporary"
            ),
        )

    with GBFSClient(
        user_agent="test",
        transport=httpx.MockTransport(handler),
        sleep=delays.append,
    ) as client:
        fetched = client.fetch("station_status", "https://example.test/status")
    assert fetched.attempt == 3
    assert calls == 3
    assert len(delays) == 2


def test_ordinary_client_error_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, request=request)

    with GBFSClient(
        user_agent="test",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    ) as client, pytest.raises(FeedFetchError):
        client.fetch("station_status", "https://example.test/status")
    assert calls == 1


def test_malformed_json_is_not_retried_as_a_transient_transport_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, request=request, content=b"not json")

    with GBFSClient(
        user_agent="test",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    ) as client, pytest.raises(FeedFetchError, match="valid JSON"):
        client.fetch("station_status", "https://example.test/status")
    assert calls == 1
