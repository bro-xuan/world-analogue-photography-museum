#!/usr/bin/env python3
"""Generate one-liner descriptions for cameras.

Tier 1: Fetch Wikipedia lead sentence for cameras with Wikipedia source URLs.
Tier 2: Template-based fallback from existing metadata fields.

Goal: 100% description coverage.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.data_io import MERGED_DIR
from src.utils.http import RateLimitedClient

CAMERAS_PATH = MERGED_DIR / "cameras.json"

# ---------------------------------------------------------------------------
# Tier 1: Wikipedia lead sentences
# ---------------------------------------------------------------------------

def _extract_title_from_url(url: str) -> str | None:
    """Extract Wikipedia article title from URL."""
    # https://en.wikipedia.org/wiki/Canon_AE-1 -> Canon_AE-1
    m = re.search(r"wikipedia\.org/wiki/(.+?)(?:#.*)?$", url)
    if m:
        return unquote(m.group(1))
    return None


def _clean_lead(text: str, camera_name: str) -> str | None:
    """Extract first 1-2 sentences from Wikipedia lead, clean up."""
    if not text:
        return None
    # Remove parenthetical pronunciation guides / Japanese etc
    text = re.sub(r"\s*\([^)]*Japanese[^)]*\)", "", text)
    text = re.sub(r"\s*\([^)]*pronounced[^)]*\)", "", text)
    # Take first 1-2 sentences (up to ~250 chars)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    result = sentences[0]
    if len(sentences) > 1 and len(result) + len(sentences[1]) < 250:
        result = result + " " + sentences[1]
    # Skip if it's basically just the name repeated
    if len(result) < 15:
        return None
    return result.strip()


async def fetch_wikipedia_descriptions(cameras: list[dict]) -> dict[str, str]:
    """Fetch Wikipedia lead sentences for cameras with Wikipedia source URLs.

    Returns dict mapping camera id -> description.
    """
    # Collect (id, title) pairs
    targets: list[tuple[str, str, str]] = []  # (camera_id, title, camera_name)
    for c in cameras:
        if c.get("description") and not c["description"].startswith("Wikimedia Commons category"):
            continue  # Already has a good description
        for s in c.get("sources", []):
            if s.get("source") == "wikipedia" and s.get("source_url"):
                title = _extract_title_from_url(s["source_url"])
                if title:
                    targets.append((c["id"], title, c.get("name", "")))
                break

    if not targets:
        print("  No Wikipedia targets found.")
        return {}

    print(f"  Fetching Wikipedia leads for {len(targets)} cameras...")
    results: dict[str, str] = {}

    # Batch by 50 titles (MediaWiki API limit)
    async with RateLimitedClient(min_delay=1.0) as client:
        for batch_start in range(0, len(targets), 50):
            batch = targets[batch_start:batch_start + 50]
            titles = "|".join(t[1] for t in batch)
            id_by_title = {t[1].replace("_", " "): (t[0], t[2]) for t in batch}

            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "prop": "extracts",
                    "exintro": "true",
                    "explaintext": "true",
                    "titles": titles,
                    "format": "json",
                    "exlimit": str(len(batch)),
                },
            )
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})

            for page in pages.values():
                title = page.get("title", "")
                extract = page.get("extract", "")
                if title in id_by_title and extract:
                    cam_id, cam_name = id_by_title[title]
                    cleaned = _clean_lead(extract, cam_name)
                    if cleaned:
                        results[cam_id] = cleaned

            done = min(batch_start + 50, len(targets))
            print(f"    Fetched {done}/{len(targets)} ({len(results)} descriptions so far)")

    print(f"  Wikipedia: got {len(results)} descriptions")
    return results


# ---------------------------------------------------------------------------
# Tier 2: Template-based fallback
# ---------------------------------------------------------------------------

def _generate_template_description(camera: dict) -> str:
    """Generate a description from existing metadata fields."""
    name = camera.get("name", "")
    mfr = camera.get("manufacturer_normalized") or camera.get("manufacturer", "")
    cam_type = camera.get("camera_type")
    year = camera.get("year_introduced")
    fmt = camera.get("film_format")

    # Normalize camera_type for display
    if cam_type and cam_type.lower() == "camera":
        cam_type = None  # Too generic

    type_str = cam_type or "camera"

    if mfr and year and fmt:
        return f"The {name} is a {type_str} produced by {mfr} in {year}. It shoots {fmt} film."
    elif mfr and year:
        return f"The {name} is a {type_str} produced by {mfr} in {year}."
    elif mfr and fmt:
        return f"The {name} is a {type_str} by {mfr}. {fmt} format."
    elif mfr:
        return f"A {type_str} by {mfr}."
    else:
        return f"An analogue {type_str}."


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def async_main():
    if not CAMERAS_PATH.exists():
        print("No merged cameras file found.")
        return

    cameras = json.loads(CAMERAS_PATH.read_text())
    total = len(cameras)
    print(f"Generating descriptions for {total} cameras...\n")

    # Count existing good descriptions
    already_good = sum(
        1 for c in cameras
        if c.get("description") and not c["description"].startswith("Wikimedia Commons category")
    )
    print(f"  Already have good descriptions: {already_good}")

    # Tier 1: Wikipedia
    print("\n--- Tier 1: Wikipedia Lead Sentences ---")
    wiki_descs = await fetch_wikipedia_descriptions(cameras)

    # Apply Wikipedia descriptions
    wiki_applied = 0
    for c in cameras:
        if c["id"] in wiki_descs:
            c["description"] = wiki_descs[c["id"]]
            wiki_applied += 1
    print(f"  Applied {wiki_applied} Wikipedia descriptions")

    # Tier 2: Template fallback for remaining
    print("\n--- Tier 2: Template-Based Fallback ---")
    template_applied = 0
    for c in cameras:
        desc = c.get("description")
        if not desc or desc.startswith("Wikimedia Commons category") or len(desc.strip()) < 5:
            c["description"] = _generate_template_description(c)
            template_applied += 1
    print(f"  Applied {template_applied} template descriptions")

    # Verify coverage
    still_missing = sum(1 for c in cameras if not c.get("description"))
    print(f"\n--- Results ---")
    print(f"  Wikipedia descriptions: {wiki_applied}")
    print(f"  Template descriptions:  {template_applied}")
    print(f"  Previously good:        {already_good}")
    print(f"  Still missing:          {still_missing}")
    print(f"  Total coverage:         {total - still_missing}/{total} ({(total - still_missing) / total * 100:.1f}%)")

    # Save
    CAMERAS_PATH.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"\nSaved updated cameras to {CAMERAS_PATH}")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
