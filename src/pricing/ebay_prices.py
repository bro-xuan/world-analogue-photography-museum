"""Fetch recent eBay sold/listed prices for cameras using the Browse API."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import time
from pathlib import Path

import httpx
import truststore

truststore.inject_into_ssl()

from src.utils.data_io import MERGED_DIR

EBAY_CLIENT_ID = os.environ["EBAY_CLIENT_ID"]
EBAY_CLIENT_SECRET = os.environ["EBAY_CLIENT_SECRET"]

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

# eBay category for Film Cameras
CATEGORY_FILM_CAMERAS = "15230"

# Rate limit: eBay Browse API allows 5000 calls/day
MIN_DELAY = 1.5


def _get_oauth_token(client: httpx.Client) -> str:
    """Get OAuth2 client credentials token."""
    creds = base64.b64encode(
        f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode()
    ).decode()
    resp = client.post(
        TOKEN_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {creds}",
        },
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _build_search_query(manufacturer: str, name: str) -> str:
    """Build a clean search query from manufacturer + model name."""
    # If name already starts with manufacturer, don't duplicate
    if name.lower().startswith(manufacturer.lower()):
        query = name
    else:
        query = f"{manufacturer} {name}"

    # Remove parenthetical suffixes that hurt search
    query = re.sub(r"\s*\(.*?\)", "", query)
    # Remove non-ASCII
    query = re.sub(r"[^\x00-\x7F]", " ", query)
    # Collapse whitespace
    query = re.sub(r"\s+", " ", query).strip()
    return query


def _median(values: list[float]) -> float:
    """Calculate median of a list."""
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def _extract_prices(data: dict, query: str) -> float | None:
    """Extract median price from search results, filtering for relevance."""
    items = data.get("itemSummaries", [])
    if not items:
        return None

    prices = []
    query_lower = query.lower()
    for item in items:
        price_info = item.get("price", {})
        currency = price_info.get("currency", "")
        value = price_info.get("value")
        if currency != "USD" or not value:
            continue
        try:
            price = float(value)
        except (ValueError, TypeError):
            continue

        # Skip unreasonable prices
        if price < 5 or price > 50000:
            continue

        prices.append(price)

    if len(prices) < 2:
        return None

    return round(_median(prices), 2)


def scrape_ebay_prices(limit: int = 0, marketplace: str = "EBAY_US") -> None:
    """Fetch eBay prices for cameras without market prices."""
    cameras_path = MERGED_DIR / "cameras.json"
    if not cameras_path.exists():
        print("No merged cameras file found.")
        return

    cameras = json.loads(cameras_path.read_text())
    print(f"Loaded {len(cameras)} cameras", flush=True)

    # Build targets: cameras without market price
    targets: list[tuple[int, str, str]] = []
    for idx, cam in enumerate(cameras):
        if cam.get("price_market_usd"):
            continue

        mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
        name = cam.get("name", "")
        if not mfr or not name:
            continue

        query = _build_search_query(mfr, name)
        if len(query) < 5:
            continue

        targets.append((idx, query, name))

    print(f"Found {len(targets)} cameras needing market prices", flush=True)
    if limit > 0:
        targets = targets[:limit]
        print(f"  Limiting to first {limit}", flush=True)

    updated = 0
    errors = 0
    skipped = 0

    with httpx.Client(timeout=30.0) as client:
        token = _get_oauth_token(client)
        print("Got OAuth token", flush=True)

        for i, (idx, query, name) in enumerate(targets):
            if (i + 1) % 50 == 0:
                print(
                    f"  Processing {i + 1}/{len(targets)}... "
                    f"({updated} prices found, {skipped} no results)",
                    flush=True,
                )
            if (i + 1) % 500 == 0:
                cameras_path.write_text(
                    json.dumps(cameras, indent=2, ensure_ascii=False)
                )
                print(f"  Saved progress at {i + 1}", flush=True)

            # Refresh token every 1500 requests (tokens last 2 hours)
            if (i + 1) % 1500 == 0:
                try:
                    token = _get_oauth_token(client)
                    print("  Refreshed OAuth token", flush=True)
                except Exception:
                    pass

            try:
                resp = client.get(
                    SEARCH_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-EBAY-C-MARKETPLACE-ID": marketplace,
                    },
                    params={
                        "q": query,
                        "category_ids": CATEGORY_FILM_CAMERAS,
                        "limit": "10",
                        "sort": "newlyListed",
                    },
                )

                if resp.status_code == 429:
                    print("  Rate limited, waiting 120s...", flush=True)
                    time.sleep(120)
                    # Retry once, then skip
                    resp = client.get(
                        SEARCH_URL,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "X-EBAY-C-MARKETPLACE-ID": marketplace,
                        },
                        params={
                            "q": query,
                            "category_ids": CATEGORY_FILM_CAMERAS,
                            "limit": "10",
                            "sort": "newlyListed",
                        },
                    )
                    if resp.status_code == 429:
                        print("  Still rate limited, stopping.", flush=True)
                        break

                if resp.status_code != 200:
                    errors += 1
                    if errors <= 10:
                        print(
                            f"  Error {resp.status_code} for '{query}': {resp.text[:200]}",
                            flush=True,
                        )
                    time.sleep(MIN_DELAY)
                    continue

                data = resp.json()
                price = _extract_prices(data, query)
                if price:
                    cameras[idx]["price_market_usd"] = price
                    updated += 1
                else:
                    skipped += 1

            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  Exception for '{query}': {e}", flush=True)

            time.sleep(MIN_DELAY)

    print(f"\neBay prices found: {updated}/{len(targets)}", flush=True)
    print(f"No results: {skipped}", flush=True)
    print(f"Errors: {errors}", flush=True)

    # Save final results
    cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"Saved to {cameras_path}", flush=True)


def main() -> None:
    import sys

    limit = 0
    marketplace = "EBAY_US"
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        if arg == "--marketplace" and i + 1 < len(args):
            marketplace = args[i + 1]

    scrape_ebay_prices(limit=limit, marketplace=marketplace)


if __name__ == "__main__":
    main()
