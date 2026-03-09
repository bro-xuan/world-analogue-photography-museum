#!/usr/bin/env python3
"""Enrich camera descriptions using Wikipedia category traversal + improved templates.

Phase 1: Fetch all camera-related Wikipedia articles via category traversal.
         Match to our cameras by name, then batch-fetch extracts.
Phase 2: Improved templates using all available metadata.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.http import RateLimitedClient

CAMERAS_PATH = PROJECT_ROOT / "data" / "merged" / "cameras.json"

# Top-level Wikipedia categories to traverse (1 level deep into subcats)
WIKI_CATEGORIES = [
    "Cameras_by_brand",
    "135_film_cameras",
    "120_film_cameras",
    "Instant_cameras",
    "Rangefinder_cameras",
    "Single-lens_reflex_cameras",
    "Twin-lens_reflex_cameras",
    "Medium_format_cameras",
    "Large_format_cameras",
    "Subminiature_cameras",
    "Box_cameras",
    "Stereo_cameras",
    "Folding_cameras",
    "Disposable_cameras",
    "Movie_cameras",
    "Cameras_introduced_in_the_1930s",
    "Cameras_introduced_in_the_1940s",
    "Cameras_introduced_in_the_1950s",
    "Cameras_introduced_in_the_1960s",
    "Cameras_introduced_in_the_1970s",
    "Cameras_introduced_in_the_1980s",
    "Cameras_introduced_in_the_1990s",
]

# Format display names
_FORMAT_NAMES = {
    "135": "35mm",
    "120": "medium format (120)",
    "220": "medium format (220)",
    "127": "127",
    "110": "110 cartridge",
    "126": "126 cartridge",
    "APS": "APS",
    "Disc": "disc",
    "4x5": "4\u00d75 large format",
    "8x10": "8\u00d710 large format",
    "Sheet film": "large format sheet film",
    "Instant Film": "instant",
    "Instax": "Instax instant",
    "Type 600": "Polaroid 600 instant",
    "SX-70": "Polaroid SX-70 instant",
    "i-Type": "Polaroid i-Type instant",
}


def _is_template_desc(desc: str) -> bool:
    if not desc:
        return True
    # Match old templates: "The X is a {type} produced by Y" or "It shoots {fmt} film."
    if "It shoots" in desc and "film." in desc:
        return True
    if " produced by " in desc and desc.count(".") <= 2 and len(desc) < 150:
        return True
    return any(p in desc for p in [
        "is a camera produced by", "is a camera by", "A camera by",
        "An analogue camera", "camera manufactured by",
        "is a camera made by", "is an analogue",
        " format.",  # "135 format." pattern
    ])


def _clean_lead(text: str) -> str | None:
    if not text or len(text) < 20:
        return None
    text = re.sub(r"\s*\([^)]*(?:Japanese|pronounced|listen|stylized|stylised|IPA)[^)]*\)", "", text, flags=re.I)
    text = re.sub(r"\[\d+\]", "", text)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    result = sentences[0]
    for s in sentences[1:3]:
        if len(result) + len(s) < 350:
            result = result + " " + s
        else:
            break
    if len(result) < 20:
        return None
    return result.strip()


# ---------------------------------------------------------------------------
# Phase 1: Wikipedia category traversal
# ---------------------------------------------------------------------------

async def _fetch_category_members(client: RateLimitedClient, category: str) -> list[str]:
    """Fetch all article titles in a Wikipedia category (pages only, no subcats)."""
    titles = []
    cmcontinue = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmtype": "page",
            "cmlimit": "500",
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        resp = await client.get("https://en.wikipedia.org/w/api.php", params=params)
        data = resp.json()
        for m in data.get("query", {}).get("categorymembers", []):
            titles.append(m["title"])
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break
    return titles


async def _fetch_subcategories(client: RateLimitedClient, category: str) -> list[str]:
    """Fetch subcategory names in a Wikipedia category."""
    subcats = []
    cmcontinue = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmtype": "subcat",
            "cmlimit": "500",
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        resp = await client.get("https://en.wikipedia.org/w/api.php", params=params)
        data = resp.json()
        for m in data.get("query", {}).get("categorymembers", []):
            # Strip "Category:" prefix
            subcats.append(m["title"].replace("Category:", ""))
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break
    return subcats


async def fetch_all_camera_articles(client: RateLimitedClient) -> set[str]:
    """Traverse Wikipedia camera categories to collect article titles."""
    all_titles: set[str] = set()
    all_cats = set(WIKI_CATEGORIES)

    # First: get subcats of top-level categories
    print("  Discovering subcategories...", flush=True)
    for cat in WIKI_CATEGORIES:
        subcats = await _fetch_subcategories(client, cat)
        all_cats.update(subcats)
    print(f"  Found {len(all_cats)} categories to scan", flush=True)

    # Then: get articles from all categories
    for i, cat in enumerate(sorted(all_cats)):
        titles = await _fetch_category_members(client, cat)
        all_titles.update(titles)
        if (i + 1) % 20 == 0:
            print(f"    Scanned {i + 1}/{len(all_cats)} categories ({len(all_titles)} articles)", flush=True)

    print(f"  Total Wikipedia camera articles found: {len(all_titles)}", flush=True)
    return all_titles


def _normalize_for_match(s: str) -> str:
    """Normalize a string for fuzzy matching."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def match_cameras_to_articles(cameras: list[dict], article_titles: set[str]) -> dict[str, str]:
    """Match camera entries to Wikipedia article titles.

    Returns dict of camera_id -> article_title.
    """
    # Build lookup: normalized title -> original title
    title_lookup: dict[str, str] = {}
    for t in article_titles:
        title_lookup[_normalize_for_match(t)] = t

    matches: dict[str, str] = {}
    for cam in cameras:
        desc = (cam.get("description") or "").strip()
        if desc and not _is_template_desc(desc):
            continue  # Already has good description

        name = cam.get("name", "")
        mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")

        # Skip obvious variants
        if "'" in name or '"' in name:
            continue

        # Try different match strategies
        candidates = []
        if mfr and name.lower().startswith(mfr.lower()):
            candidates.append(name)
        if mfr:
            candidates.append(f"{mfr} {name}")
        candidates.append(name)

        for cand in candidates:
            norm = _normalize_for_match(cand)
            if norm in title_lookup:
                matches[cam["id"]] = title_lookup[norm]
                break

    return matches


async def batch_fetch_extracts(client: RateLimitedClient, titles: list[str]) -> dict[str, str]:
    """Batch-fetch Wikipedia extracts, 50 at a time."""
    results: dict[str, str] = {}

    for batch_start in range(0, len(titles), 50):
        batch = titles[batch_start:batch_start + 50]
        resp = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "prop": "extracts",
                "exintro": "true",
                "explaintext": "true",
                "titles": "|".join(batch),
                "format": "json",
                "exlimit": str(len(batch)),
            },
        )
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title", "")
            extract = page.get("extract", "")
            if extract:
                cleaned = _clean_lead(extract)
                if cleaned:
                    results[title] = cleaned

        done = min(batch_start + 50, len(titles))
        if done % 200 == 0 or done == len(titles):
            print(f"    Fetched extracts {done}/{len(titles)}", flush=True)

    return results


# ---------------------------------------------------------------------------
# Phase 2: Rich template descriptions
# ---------------------------------------------------------------------------

def _format_display(fmt: str | None) -> str | None:
    if not fmt:
        return None
    return _FORMAT_NAMES.get(fmt, fmt)


def _generate_rich_description(cam: dict) -> str:
    name = cam.get("name", "")
    mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
    cam_type = cam.get("camera_type")
    year = cam.get("year_introduced")
    year_end = cam.get("year_discontinued")
    fmt = cam.get("film_format")
    lens = cam.get("lens_mount")
    shutter = cam.get("shutter_speed_range")
    metering = cam.get("metering")
    weight = cam.get("weight_g")

    type_lower = (cam_type or "").lower()
    if not cam_type or type_lower == "camera":
        if lens and "slr" in (lens or "").lower():
            cam_type = "SLR camera"
        elif fmt and fmt in ("120", "220"):
            cam_type = "medium format camera"
        elif fmt and fmt in ("4x5", "8x10", "Sheet film"):
            cam_type = "large format camera"
        elif fmt and fmt in ("Instant Film", "Type 600", "SX-70", "i-Type", "Instax"):
            cam_type = "instant camera"
        else:
            cam_type = "camera"
    elif "slr" in type_lower or "reflex" in type_lower:
        if "twin" in type_lower or "tlr" in type_lower:
            cam_type = "twin-lens reflex (TLR) camera"
        else:
            cam_type = "SLR camera"
    elif "rangefinder" in type_lower:
        cam_type = "rangefinder camera"
    elif "point" in type_lower or "compact" in type_lower:
        cam_type = "compact camera"
    elif "folding" in type_lower:
        cam_type = "folding camera"
    elif "box" in type_lower:
        cam_type = "box camera"
    elif "stereo" in type_lower:
        cam_type = "stereo camera"
    elif "subminiature" in type_lower:
        cam_type = "subminiature camera"

    fmt_display = _format_display(fmt)
    parts = []

    # Opening sentence
    fmt_prefix = f"{fmt_display} " if fmt_display else ""
    if mfr and year and year_end:
        parts.append(f"The {name} is a {fmt_prefix}{cam_type} produced by {mfr} from {year} to {year_end}.")
    elif mfr and year:
        parts.append(f"The {name} is a {fmt_prefix}{cam_type} introduced by {mfr} in {year}.")
    elif mfr:
        parts.append(f"The {name} is a {fmt_prefix}{cam_type} made by {mfr}.")
    else:
        parts.append(f"The {name} is an analogue {fmt_prefix}{cam_type}.")

    # Technical details
    tech_bits = []
    if lens:
        tech_bits.append(f"{lens} lens mount")
    if shutter:
        s = shutter if len(shutter) <= 60 else shutter[:57] + "..."
        tech_bits.append(f"{s} shutter")
    if metering:
        tech_bits.append(f"{metering} metering")
    if tech_bits:
        parts.append("It features " + ", ".join(tech_bits) + ".")

    if weight and weight > 0:
        kg = weight / 1000
        parts.append(f"It weighs {kg:.1f} kg." if kg >= 1 else f"It weighs {weight} g.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def async_main():
    if not CAMERAS_PATH.exists():
        print("No merged cameras file found.")
        return

    cameras = json.loads(CAMERAS_PATH.read_text())
    total = len(cameras)

    good_count = sum(1 for c in cameras if not _is_template_desc(c.get("description", "")))
    template_count = sum(1 for c in cameras if _is_template_desc(c.get("description", "")) and (c.get("description") or "").strip())
    missing_count = sum(1 for c in cameras if not (c.get("description") or "").strip())

    print(f"Current state ({total} cameras):", flush=True)
    print(f"  Good descriptions: {good_count}", flush=True)
    print(f"  Template descriptions: {template_count}", flush=True)
    print(f"  Missing descriptions: {missing_count}", flush=True)

    # Phase 1: Wikipedia
    print(f"\n--- Phase 1: Wikipedia Category Traversal ---", flush=True)
    async with RateLimitedClient(min_delay=0.3) as client:
        article_titles = await fetch_all_camera_articles(client)

        # Match our cameras to articles
        print(f"\n  Matching cameras to articles...", flush=True)
        matches = match_cameras_to_articles(cameras, article_titles)
        print(f"  Matched {len(matches)} cameras to Wikipedia articles", flush=True)

        # Batch-fetch extracts for matched articles
        unique_titles = list(set(matches.values()))
        print(f"  Fetching extracts for {len(unique_titles)} unique articles...", flush=True)
        extracts = await batch_fetch_extracts(client, unique_titles)
        print(f"  Got {len(extracts)} usable extracts", flush=True)

    # Apply Wikipedia descriptions
    wiki_applied = 0
    cam_by_id = {c["id"]: c for c in cameras}
    for cam_id, article_title in matches.items():
        if article_title in extracts:
            cam_by_id[cam_id]["description"] = extracts[article_title]
            wiki_applied += 1
    print(f"  Applied {wiki_applied} Wikipedia descriptions", flush=True)

    # Phase 2: Improved templates for the rest
    print(f"\n--- Phase 2: Enriched Templates ---", flush=True)
    template_upgraded = 0
    new_generated = 0
    for c in cameras:
        desc = (c.get("description") or "").strip()
        if not desc:
            c["description"] = _generate_rich_description(c)
            new_generated += 1
        elif _is_template_desc(desc):
            c["description"] = _generate_rich_description(c)
            template_upgraded += 1

    print(f"  Upgraded {template_upgraded} template descriptions", flush=True)
    print(f"  Generated {new_generated} new descriptions", flush=True)

    # Final stats
    final_good = sum(1 for c in cameras if not _is_template_desc(c.get("description", "")))
    final_missing = sum(1 for c in cameras if not (c.get("description") or "").strip())

    print(f"\n--- Results ---", flush=True)
    print(f"  Good descriptions: {good_count} -> {final_good} (+{final_good - good_count})", flush=True)
    print(f"  Missing: {missing_count} -> {final_missing}", flush=True)
    print(f"  Total coverage: {total - final_missing}/{total}", flush=True)

    # Save
    CAMERAS_PATH.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"\nSaved to {CAMERAS_PATH}", flush=True)

    # Show samples
    print(f"\n--- Sample descriptions ---", flush=True)
    shown = 0
    for c in cameras:
        if c["id"] in matches and matches[c["id"]] in extracts:
            print(f"\n[WIKI] {c.get('manufacturer_normalized','')} {c['name']}:", flush=True)
            print(f"  {c['description'][:250]}", flush=True)
            shown += 1
            if shown >= 5:
                break

    shown = 0
    for c in cameras:
        d = c.get("description", "")
        if d and "It features" in d and c["id"] not in matches:
            print(f"\n[RICH] {c.get('manufacturer_normalized','')} {c['name']}:", flush=True)
            print(f"  {d[:250]}", flush=True)
            shown += 1
            if shown >= 3:
                break


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
