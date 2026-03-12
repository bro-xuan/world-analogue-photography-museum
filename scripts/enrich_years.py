#!/usr/bin/env python3
"""Enrich cameras missing year_introduced by scraping their source pages."""

import asyncio
import json
import re
import sys
import argparse
from pathlib import Path

sys.path.insert(0, ".")

from bs4 import BeautifulSoup
from src.utils.http import RateLimitedClient

DATA_PATH = Path("data/merged/cameras.json")
CHECKPOINT_EVERY = 200


def _extract_year_from_collectiblend(html: str) -> tuple[int | None, int | None]:
    """Extract year from collectiblend detail page.

    The year appears in the description text like:
    - "1985. 35mm SLR camera."
    - "c1960. 120 roll film."
    - "1959-1975. 35mm rangefinder."
    - "c1950s. Box camera."
    """
    soup = BeautifulSoup(html, "lxml")

    # Look for the description paragraph — usually in a <p> or <td> containing the year pattern
    # The description is typically the first substantial text block after the camera name
    text_blocks = []

    # Try meta description first
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        text_blocks.append(meta["content"])

    # Try all paragraphs and table cells
    for tag in soup.find_all(["p", "td", "div"]):
        text = tag.get_text(strip=True)
        if text and len(text) > 10:
            text_blocks.append(text)

    for text in text_blocks:
        # Match patterns like "1985." or "c1960." or "1959-1975." or "c1950s."
        # Year range: "1959-1975"
        m = re.match(r"^c?\.?\s*(\d{4})\s*[-–]\s*(\d{4})", text)
        if m:
            return int(m.group(1)), int(m.group(2))

        # Single year: "1985." or "c1960."
        m = re.match(r"^c?\.?\s*(\d{4})\b", text)
        if m:
            year = int(m.group(1))
            if 1820 <= year <= 2030:
                return year, None

        # Decade: "c1950s"
        m = re.match(r"^c?\.?\s*(\d{4})s\b", text)
        if m:
            year = int(m.group(1))
            if 1820 <= year <= 2030:
                return year, None

    return None, None


def _extract_year_from_camerawiki(html: str) -> tuple[int | None, int | None]:
    """Extract year from camera-wiki.org page."""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text()

    # Look for common patterns in camerawiki articles:
    # "introduced in 1985", "released in 1960", "made from 1955", "produced from 1970 to 1980"
    patterns = [
        r"(?:introduced|released|launched|made|produced|manufactured|marketed|sold|appeared|available)\s+(?:in|from|around|circa|ca\.?|c\.?)\s*(\d{4})",
        r"(?:from|in)\s+(\d{4})\s*(?:to|[-–])\s*(\d{4})",
        r"(\d{4})\s*(?:to|[-–])\s*(\d{4})",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            if 1820 <= year <= 2030:
                year_end = int(m.group(2)) if m.lastindex >= 2 else None
                return year, year_end

    # Fallback: look for a 4-digit year in the first few sentences
    # Only match years in reasonable photography range
    first_text = text[:2000]
    years = [int(y) for y in re.findall(r"\b(1[89]\d{2}|20[0-2]\d)\b", first_text)]
    if years:
        return min(years), None

    return None, None


async def enrich_years(limit: int = 0, source_filter: str = "all"):
    cameras = json.loads(DATA_PATH.read_text())

    no_year = [c for c in cameras if not c.get("year_introduced")]
    print(f"Total cameras: {len(cameras)}, without year: {len(no_year)}")

    # Filter by source type
    if source_filter == "collectiblend":
        targets = [c for c in no_year if any(s["source"] == "collectiblend" for s in c.get("sources", []))]
    elif source_filter == "camerawiki":
        targets = [c for c in no_year if any(s["source"] == "camerawiki" for s in c.get("sources", []))]
    else:
        # Prioritize collectiblend first, then camerawiki
        coll = [c for c in no_year if any(s["source"] == "collectiblend" for s in c.get("sources", []))]
        cwiki = [c for c in no_year if any(s["source"] == "camerawiki" for s in c.get("sources", [])) and c not in coll]
        targets = coll + cwiki

    if limit > 0:
        targets = targets[:limit]

    print(f"Targets to process: {len(targets)}")

    # Build lookup for fast updates
    cam_by_id = {c["id"]: c for c in cameras if c.get("id")}

    found = 0
    errors = 0
    processed = 0

    async with RateLimitedClient(min_delay=1.5, verify_ssl=False) as client:
        for i, cam in enumerate(targets):
            name = cam["name"]
            sources = {s["source"]: s.get("source_url", "") for s in cam.get("sources", [])}

            year_intro = None
            year_disc = None

            # Try collectiblend first
            if "collectiblend" in sources and sources["collectiblend"]:
                url = sources["collectiblend"]
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        year_intro, year_disc = _extract_year_from_collectiblend(resp.text)
                    elif resp.status_code == 404:
                        pass  # Page gone
                    else:
                        print(f"  HTTP {resp.status_code} for {url}")
                except Exception as e:
                    errors += 1
                    print(f"  Error fetching {url}: {e}")

            # Try camerawiki if no year found
            if year_intro is None and "camerawiki" in sources and sources["camerawiki"]:
                url = sources["camerawiki"]
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        year_intro, year_disc = _extract_year_from_camerawiki(resp.text)
                except Exception as e:
                    errors += 1
                    print(f"  Error fetching {url}: {e}")

            processed += 1

            if year_intro:
                cam["year_introduced"] = year_intro
                if year_disc:
                    cam["year_discontinued"] = year_disc
                # Update in main list too
                if cam.get("id") and cam["id"] in cam_by_id:
                    cam_by_id[cam["id"]]["year_introduced"] = year_intro
                    if year_disc:
                        cam_by_id[cam["id"]]["year_discontinued"] = year_disc
                found += 1
                print(f"  [{processed}/{len(targets)}] {name}: {year_intro}{f'-{year_disc}' if year_disc else ''}")
            else:
                if processed % 50 == 0:
                    print(f"  [{processed}/{len(targets)}] (no year found for {name})")

            # Checkpoint
            if processed % CHECKPOINT_EVERY == 0:
                DATA_PATH.write_text(json.dumps(cameras, ensure_ascii=False))
                print(f"  --- Checkpoint at {processed}: {found} years found so far ---")

    # Final save
    DATA_PATH.write_text(json.dumps(cameras, ensure_ascii=False))

    print(f"\nDone. Processed: {processed}, Found years: {found}, Errors: {errors}")
    print(f"Hit rate: {100*found/max(processed,1):.1f}%")

    # Updated stats
    total_with_year = sum(1 for c in cameras if c.get("year_introduced"))
    print(f"Total cameras with year now: {total_with_year}/{len(cameras)} ({100*total_with_year/len(cameras):.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Enrich cameras with missing years")
    parser.add_argument("--limit", type=int, default=0, help="Max cameras to process (0=all)")
    parser.add_argument("--source", choices=["all", "collectiblend", "camerawiki"], default="all")
    args = parser.parse_args()

    asyncio.run(enrich_years(limit=args.limit, source_filter=args.source))


if __name__ == "__main__":
    main()
