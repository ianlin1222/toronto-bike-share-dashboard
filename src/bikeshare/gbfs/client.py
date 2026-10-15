from __future__ import annotations

import json
import random
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from bikeshare.gbfs.models import FetchedFeed
from bikeshare.gbfs.parser import feed_last_updated, feed_ttl


class FeedFetchError(RuntimeError):
    def __init__(self, message: str, *, url: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class GBFSClient:
    def __init__(
        self,
        *,
        user_agent: str,
        max_attempts: int = 3,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.max_attempts = max_attempts
        if sleep is None:
            from time import sleep as blocking_sleep

            sleep = blocking_sleep
        self._sleep = sleep
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(10.0, connect=5.0),
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            transport=transport,
        )

    def __enter__(self) -> GBFSClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fetch(self, name: str, url: str) -> FetchedFeed:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            retrieved_at = datetime.now(tz=UTC)
            try:
                response = self._client.get(url)
                if (
                    response.status_code == 429 or response.status_code >= 500
                ) and attempt < self.max_attempts:
                    self._sleep(self._retry_delay(response, attempt))
                    continue
                response.raise_for_status()
                try:
                    payload: Any = response.json()
                except json.JSONDecodeError as error:
                    raise FeedFetchError(
                        "feed response is not valid JSON",
                        url=url,
                        status_code=response.status_code,
                    ) from error
                if not isinstance(payload, dict):
                    raise FeedFetchError(
                        "feed response root is not an object",
                        url=url,
                        status_code=response.status_code,
                    )
                return FetchedFeed(
                    name=name,
                    url=str(response.url),
                    retrieved_at=retrieved_at,
                    status_code=response.status_code,
                    body=response.content,
                    payload=payload,
                    attempt=attempt,
                    feed_last_updated=feed_last_updated(payload),
                    ttl_seconds=feed_ttl(payload),
                    cache_headers={
                        key.lower(): value
                        for key, value in response.headers.items()
                        if key.lower() in {"age", "cache-control", "date", "etag", "last-modified", "retry-after"}
                    },
                )
            except (httpx.HTTPError, FeedFetchError) as error:
                last_error = error
                retryable = not isinstance(error, FeedFetchError)
                if isinstance(error, httpx.HTTPStatusError):
                    retryable = error.response.status_code == 429 or error.response.status_code >= 500
                if not retryable or attempt >= self.max_attempts:
                    break
                self._sleep(attempt + random.uniform(0, 0.25))
        status_code = (
            last_error.response.status_code
            if isinstance(last_error, httpx.HTTPStatusError)
            else getattr(last_error, "status_code", None)
        )
        raise FeedFetchError(
            f"failed to fetch {name} after {self.max_attempts} attempts: {last_error}",
            url=url,
            status_code=status_code,
        ) from last_error

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0), 30)
            except ValueError:
                try:
                    target = parsedate_to_datetime(retry_after).astimezone(UTC)
                    return min(max((target - datetime.now(tz=UTC)).total_seconds(), 0), 30)
                except (TypeError, ValueError, OverflowError):
                    pass
        return float(2 ** (attempt - 1) + random.uniform(0, 0.25))
