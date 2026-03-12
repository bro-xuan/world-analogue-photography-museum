#!/usr/bin/env python3
"""Wrapper to run eBay scrapling scraper on a separate data file."""
import json
import sys

sys.path.insert(0, ".")

from pathlib import Path
from src.pricing.ebay_scrape import (
    _build_search_query,
    _build_ebay_url,
    _extract_sold_prices,
    _fetch_page,
)

DATA_PATH = Path("data/merged/cameras_for_ebay.json")


def main():
    limit = 0
    force = False
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        if arg == "--force":
            force = True

    cameras = json.loads(DATA_PATH.read_text())
    print(f"Loaded {len(cameras)} cameras from {DATA_PATH}", flush=True)

    targets = []
    for idx, cam in enumerate(cameras):
        has_price = cam.get("price_market_usd")
        if has_price and not force:
            continue
        if has_price and force and cam.get("price_market_source") == "ebay":
            continue

        mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
        name = cam.get("name", "")
        if not mfr or not name:
            continue

        query = _build_search_query(mfr, name)
        if len(query) < 5:
            continue
        targets.append((idx, query, name))

    mode_label = "all (force refresh)" if force else "missing only"
    print(f"Found {len(targets)} cameras to price ({mode_label})", flush=True)
    if limit > 0:
        targets = targets[:limit]
        print(f"  Limiting to first {limit}", flush=True)

    updated = 0
    errors = 0
    skipped = 0
    consecutive_failures = 0

    for i, (idx, query, name) in enumerate(targets):
        if (i + 1) % 10 == 0:
            print(
                f"  Processing {i + 1}/{len(targets)}... "
                f"({updated} prices, {skipped} no results, {errors} errors)",
                flush=True,
            )
        if (i + 1) % 100 == 0:
            DATA_PATH.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
            print(f"  Saved checkpoint at {i + 1}", flush=True)

        try:
            url = _build_ebay_url(query)
            page = _fetch_page(url)

            if page is None:
                errors += 1
                consecutive_failures += 1
                if errors <= 10:
                    print(f"  Failed to load '{query}'", flush=True)
                if consecutive_failures >= 5:
                    print("  5 consecutive failures — blocked. Stopping.", flush=True)
                    break
                continue

            consecutive_failures = 0
            price = _extract_sold_prices(page.html_content, query)
            if price:
                cameras[idx]["price_market_usd"] = price
                cameras[idx]["price_market_source"] = "ebay"
                updated += 1
                print(f"    {name}: ${price}", flush=True)
            else:
                skipped += 1

        except Exception as e:
            errors += 1
            consecutive_failures += 1
            if errors <= 10:
                print(f"  Exception for '{query}': {e}", flush=True)
            if consecutive_failures >= 5:
                print("  5 consecutive failures — stopping.", flush=True)
                break

    print(f"\neBay sold prices found: {updated}/{len(targets)}", flush=True)
    print(f"No results: {skipped}", flush=True)
    print(f"Errors: {errors}", flush=True)

    DATA_PATH.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"Saved to {DATA_PATH}", flush=True)


if __name__ == "__main__":
    main()
