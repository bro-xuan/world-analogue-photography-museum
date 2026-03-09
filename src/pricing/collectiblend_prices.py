"""Scrape current market values from collectiblend.com detail pages."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from src.utils.data_io import MERGED_DIR
from src.utils.http import RateLimitedClient


def _parse_market_price(html: str) -> float | None:
    """Parse the market value from a collectiblend detail page.

    Look for pricing table/div. Collectiblend shows condition-based pricing
    (Average, Very Good, Mint, etc). Extract the "Average" condition value.
    Parse dollar amounts like "$125" or "$1,250".
    Returns the price as a float or None if not found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Strategy 1: Look for a table with condition/price columns
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            cell_texts = [c.get_text(strip=True).lower() for c in cells]
            # Look for row containing "average" in a condition column
            for i, text in enumerate(cell_texts):
                if "average" in text:
                    # Look for dollar amount in adjacent cells
                    for j, ct in enumerate(cell_texts):
                        if j != i:
                            m = re.search(r'\$\s*([\d,]+(?:\.\d{2})?)', ct)
                            if m:
                                return float(m.group(1).replace(",", ""))

    # Strategy 2: Look for text containing "Average" near a dollar amount
    text = soup.get_text()
    # Find "average" followed by a price
    m = re.search(r'average[^$]*\$\s*([\d,]+(?:\.\d{2})?)', text, re.I)
    if m:
        return float(m.group(1).replace(",", ""))

    # Strategy 3: Look for any "value" or "price" indicator
    m = re.search(r'(?:value|price|worth)[^$]*\$\s*([\d,]+(?:\.\d{2})?)', text, re.I)
    if m:
        val = float(m.group(1).replace(",", ""))
        if val > 0:
            return val

    return None


async def _scrape_market_prices(limit: int = 0) -> None:
    """Scrape market prices from collectiblend detail pages."""
    cameras_path = MERGED_DIR / "cameras.json"
    if not cameras_path.exists():
        print("No merged cameras file found. Run merge first.")
        return

    cameras = json.loads(cameras_path.read_text())

    # Find cameras with collectiblend source URLs
    targets: list[tuple[int, str]] = []
    for idx, cam in enumerate(cameras):
        for src in cam.get("sources", []):
            if src.get("source") == "collectiblend" and src.get("source_url"):
                url = src["source_url"]
                if url.endswith(".html"):
                    targets.append((idx, url))
                    break

    # Skip cameras that already have market prices
    targets = [(idx, url) for idx, url in targets if not cameras[idx].get("price_market_usd")]
    print(f"Found {len(targets)} cameras needing market prices")
    if limit > 0:
        targets = targets[:limit]
        print(f"  Limiting to first {limit}")

    updated = 0
    errors = 0
    async with RateLimitedClient(min_delay=2.0) as client:
        for i, (idx, url) in enumerate(targets):
            if (i + 1) % 50 == 0:
                print(f"  Processing {i + 1}/{len(targets)}... ({updated} prices found)", flush=True)
                # Save progress every 500
            if (i + 1) % 500 == 0:
                cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
                print(f"  Saved progress at {i + 1}", flush=True)

            try:
                resp = await client.get(url)
                price = _parse_market_price(resp.text)
                if price and price > 0:
                    cameras[idx]["price_market_usd"] = price
                    updated += 1
            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  Error fetching {url}: {e}", flush=True)

    print(f"\nMarket prices found: {updated}/{len(targets)}", flush=True)
    print(f"Errors: {errors}", flush=True)

    # Save updated cameras
    cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"Saved updated cameras to {cameras_path}", flush=True)


def main() -> None:
    """Entry point for collectiblend market price scraping."""
    import sys

    limit = 0
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--limit" and i < len(sys.argv):
            limit = int(sys.argv[i + 1])
    asyncio.run(_scrape_market_prices(limit=limit))


if __name__ == "__main__":
    main()
