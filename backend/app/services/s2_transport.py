"""
Rate-limited transport for the Semantic Scholar API.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"


class S2Transport:
    """
    Async HTTP transport for the S2 API.

    Rate limiting: token-bucket (configurable).
    Backoff: exponential on 429, up to max_retries.
    API key: passed as x-api-key if configured.
    """

    def __init__(
        self,
        api_key: str | None = None,
        rate_limit: float = 0.9,
        max_retries: int = 5,
    ):
        self._api_key = api_key
        self._rate_limit = 10.0 if api_key else rate_limit
        self._max_retries = max_retries
        self._tokens = self._rate_limit
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if self._api_key:
                headers["x-api-key"] = self._api_key
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
                limits=httpx.Limits(max_connections=5),
            )
        return self._client

    async def _acquire_token(self) -> None:
        """Block until a rate-limit token is available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self._rate_limit,
                self._tokens + elapsed * self._rate_limit,
            )
            self._last_refill = now

            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate_limit
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict | None:
        """GET a path under the S2 API base, with rate limiting and backoff."""
        url = f"{S2_API_BASE}/{path.lstrip('/')}"
        client = await self._get_client()

        for attempt in range(self._max_retries):
            await self._acquire_token()
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 429:
                    wait = 2.0 * (2**attempt)
                    logger.warning("S2 429 rate-limit, retry in %.1fs (%s)", wait, path)
                    await asyncio.sleep(wait)
                    continue
                if response.status_code == 404:
                    return None
                logger.error(
                    "S2 %s: %s (%s)", response.status_code, response.text[:200], path
                )
                return None
            except httpx.TimeoutException:
                wait = 2.0 * (2**attempt)
                logger.warning("S2 timeout, retry in %.1fs (%s)", wait, path)
                await asyncio.sleep(wait)
            except Exception as exc:
                logger.error("S2 transport error: %s (%s)", exc, path)
                return None
        return None

    async def post(
        self,
        path: str,
        json_body: dict | list | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict | None:
        """POST to a path under the S2 API base, with rate limiting and backoff."""
        url = f"{S2_API_BASE}/{path.lstrip('/')}"
        client = await self._get_client()

        for attempt in range(self._max_retries):
            await self._acquire_token()
            try:
                response = await client.post(url, json=json_body, params=params)
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 429:
                    wait = 2.0 * (2**attempt)
                    logger.warning("S2 429 rate-limit, retry in %.1fs (%s)", wait, path)
                    await asyncio.sleep(wait)
                    continue
                if response.status_code == 404:
                    return None
                logger.error(
                    "S2 %s: %s (%s)", response.status_code, response.text[:200], path
                )
                return None
            except httpx.TimeoutException:
                wait = 2.0 * (2**attempt)
                logger.warning("S2 timeout, retry in %.1fs (%s)", wait, path)
                await asyncio.sleep(wait)
            except Exception as exc:
                logger.error("S2 transport error: %s (%s)", exc, path)
                return None
        return None

    async def search(self, query: str, limit: int = 1) -> list[dict]:
        """Search papers by title via the S2 search API."""
        data = await self.get(
            "paper/search",
            params={"query": query, "limit": limit, "fields": "paperId,title"},
        )
        if data and "data" in data:
            return data["data"]
        return []

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
