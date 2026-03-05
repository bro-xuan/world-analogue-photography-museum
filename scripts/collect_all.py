#!/usr/bin/env python3
"""Run all collectors, merge results, and verify data quality."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.normalization.merge import main as merge_main
from src.utils.data_io import MERGED_DIR


def run_collectors():
    """Run all collectors in sequence."""
    print("\n" + "=" * 60)
    print("PHASE 1: DATA COLLECTION")
    print("=" * 60)

    # Wikidata
    print("\n--- Wikidata Collector ---")
    try:
        from src.collectors.wikidata import main as wikidata_main
        wikidata_main()
    except Exception as e:
        print(f"  WARNING: Wikidata collector failed: {e}")

    # Flickr
    print("\n--- Flickr Collector ---")
    try:
        from src.collectors.flickr import main as flickr_main
        flickr_main()
    except Exception as e:
        print(f"  WARNING: Flickr collector failed: {e}")

    # Wikipedia
    print("\n--- Wikipedia Collector ---")
    try:
        from src.collectors.wikipedia import main as wikipedia_main
        wikipedia_main()
    except Exception as e:
        print(f"  WARNING: Wikipedia collector failed: {e}")

    # Chinese cameras (targeted camera-wiki.org crawl)
    print("\n--- Chinese Cameras Collector (camera-wiki.org) ---")
    try:
        from src.collectors.chinese_cameras import main as chinese_cameras_main
        chinese_cameras_main()
    except Exception as e:
        print(f"  WARNING: Chinese cameras collector failed: {e}")

    # chinesecamera.com (国产相机档案)
    print("\n--- Chinese Camera Archive (chinesecamera.com) ---")
    try:
        from src.collectors.chinesecamera import main as chinesecamera_main
        chinesecamera_main()
    except Exception as e:
        print(f"  WARNING: chinesecamera.com collector failed: {e}")

    # Camera-wiki.org
    print("\n--- Camera-wiki.org Collector ---")
    try:
        from src.collectors.camerawiki import main as camerawiki_main
        camerawiki_main()
    except Exception as e:
        print(f"  WARNING: Camera-wiki collector failed: {e}")

    # Collectiblend
    print("\n--- Collectiblend Collector ---")
    try:
        from src.collectors.collectiblend import main as collectiblend_main
        collectiblend_main()
    except Exception as e:
        print(f"  WARNING: Collectiblend collector failed: {e}")


def run_merge():
    """Run the merge pipeline."""
    print("\n" + "=" * 60)
    print("PHASE 2: MERGE & DEDUPLICATION")
    print("=" * 60)
    merge_main()


def verify():
    """Run verification checks on merged data."""
    print("\n" + "=" * 60)
    print("PHASE 3: VERIFICATION")
    print("=" * 60)

    cameras_path = MERGED_DIR / "cameras.json"
    films_path = MERGED_DIR / "films.json"

    if not cameras_path.exists():
        print("  ERROR: No merged cameras file found")
        return False
    if not films_path.exists():
        print("  ERROR: No merged films file found")
        return False

    cameras = json.loads(cameras_path.read_text())
    films = json.loads(films_path.read_text())

    ok = True

    # 1. Counts
    print(f"\n  Total cameras: {len(cameras)}")
    print(f"  Total films:   {len(films)}")

    # 2. Major manufacturers represented
    REQUIRED_CAMERA_MANUFACTURERS = [
        "Canon", "Nikon", "Pentax", "Olympus", "Minolta", "Leica",
        "Hasselblad", "Mamiya", "Rollei", "Yashica", "Contax", "Fujifilm",
        "Kodak", "Polaroid", "Seagull", "Zenit", "FED", "Praktica",
    ]
    cam_manufacturers = {c.get("manufacturer_normalized", c.get("manufacturer", "")) for c in cameras}
    missing_mfrs = [m for m in REQUIRED_CAMERA_MANUFACTURERS if m not in cam_manufacturers]
    if missing_mfrs:
        print(f"\n  WARNING: Missing camera manufacturers: {', '.join(missing_mfrs)}")
        ok = False
    else:
        print(f"\n  All {len(REQUIRED_CAMERA_MANUFACTURERS)} major camera manufacturers represented")

    # 3. Film coverage
    REQUIRED_FILM_NAMES = [
        "Tri-X", "Portra", "HP5", "Velvia", "Ektar", "Gold",
        "Delta", "FP4", "Acros",
    ]
    film_names_lower = " ".join(f.get("name", "").lower() for f in films)
    missing_films = [f for f in REQUIRED_FILM_NAMES if f.lower() not in film_names_lower]
    if missing_films:
        print(f"  WARNING: Missing film stocks: {', '.join(missing_films)}")
    else:
        print(f"  All {len(REQUIRED_FILM_NAMES)} key film stocks represented")

    # 4. Image coverage
    cameras_with_images = sum(1 for c in cameras if c.get("images"))
    image_pct = (cameras_with_images / max(len(cameras), 1)) * 100
    print(f"\n  Image coverage: {cameras_with_images}/{len(cameras)} cameras ({image_pct:.1f}%)")
    if image_pct < 10:
        print("  NOTE: Image coverage is low — run scripts/download_images.py to download")

    # 5. Dedup check
    seen_keys = set()
    dupes = 0
    for c in cameras:
        key = (c.get("manufacturer_normalized", "").lower(), c.get("name", "").lower())
        if key in seen_keys:
            dupes += 1
        seen_keys.add(key)
    dupe_rate = (dupes / max(len(cameras), 1)) * 100
    print(f"\n  Duplicate rate: {dupes}/{len(cameras)} ({dupe_rate:.1f}%)")
    if dupe_rate > 1:
        print("  WARNING: Duplicate rate exceeds 1% target")
        ok = False

    # 6. Spot-check random cameras
    print(f"\n  Spot-checking 10 random cameras:")
    sample = random.sample(cameras, min(10, len(cameras)))
    for c in sample:
        name = c.get("name", "?")
        mfr = c.get("manufacturer_normalized", c.get("manufacturer", "?"))
        year = c.get("year_introduced", "?")
        country = c.get("manufacturer_country", "?")
        sources = [s.get("source", "?") for s in c.get("sources", [])]
        print(f"    {mfr} {name} ({year}, {country}) — sources: {', '.join(sources)}")

    # 7. Source distribution
    print(f"\n  Source distribution (cameras):")
    source_counts: dict[str, int] = {}
    for c in cameras:
        for s in c.get("sources", []):
            src = s.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {src}: {count}")

    print(f"\n  Source distribution (films):")
    source_counts = {}
    for f in films:
        for s in f.get("sources", []):
            src = s.get("source", "unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {src}: {count}")

    # 8. Country distribution (new)
    print(f"\n  Country distribution (cameras):")
    country_counts: dict[str, int] = {}
    for c in cameras:
        country = c.get("manufacturer_country", "Unknown")
        country_counts[country] = country_counts.get(country, 0) + 1
    for country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
        print(f"    {country}: {count}")

    return ok


def main():
    print("World Analogue Photography Museum — Data Collection")
    print("=" * 60)

    run_collectors()
    run_merge()
    success = verify()

    print("\n" + "=" * 60)
    if success:
        print("COLLECTION COMPLETE — all checks passed")
    else:
        print("COLLECTION COMPLETE — some checks had warnings (see above)")
    print("=" * 60)


if __name__ == "__main__":
    main()
