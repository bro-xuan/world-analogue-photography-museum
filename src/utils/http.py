"""Shared HTTP client with rate limiting and retry logic."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx

DEFAULT_HEADERS = {
    "User-Agent": "AnalogueMuseumBot/0.1 (https://github.com/world-analogue-photography-museum; museum-data@example.org) python-httpx/0.28"
}


class RateLimitedClient:
    """HTTP client that enforces a minimum delay between requests."""

    def __init__(self, min_delay: float = 1.0, max_retries: int = 3, verify_ssl: bool = True):
        self.min_delay = min_delay
        self.max_retries = max_retries
        self._last_request_time = 0.0
        self._client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=30.0,
            follow_redirects=True,
            verify=verify_ssl,
        )

    async def get(self, url: str, **kwargs) -> httpx.Response:
        for attempt in range(self.max_retries):
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.min_delay:
                await asyncio.sleep(self.min_delay - elapsed)

            self._last_request_time = time.monotonic()
            try:
                resp = await self._client.get(url, **kwargs)
                if resp.status_code in (429, 403):
                    wait = int(resp.headers.get("Retry-After", 30 * (attempt + 1)))
                    print(f"  Rate limited ({resp.status_code}), waiting {wait}s...")
                    await asyncio.sleep(wait)
                    # Increase min_delay after rate limiting to avoid repeated hits
                    self.min_delay = min(self.min_delay * 1.5, 10.0)
                    continue
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                if attempt < self.max_retries - 1 and e.response.status_code >= 500:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                raise

        raise RuntimeError(f"Max retries exceeded for {url}")

    async def download_file(self, url: str, dest: Path) -> bool:
        """Download a file to dest path. Returns True on success."""
        for attempt in range(self.max_retries):
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.min_delay:
                await asyncio.sleep(self.min_delay - elapsed)

            self._last_request_time = time.monotonic()
            try:
                async with self._client.stream("GET", url) as resp:
                    if resp.status_code in (429, 403):
                        wait = int(resp.headers.get("Retry-After", 30 * (attempt + 1)))
                        print(f"  Rate limited ({resp.status_code}), waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    if resp.status_code >= 400:
                        print(f"  HTTP {resp.status_code} for {url}")
                        return False

                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with open(dest, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                return True
            except (httpx.HTTPError, OSError) as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                print(f"  Download failed for {url}: {e}")
                return False

        print(f"  Max retries exceeded downloading {url}")
        return False

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
