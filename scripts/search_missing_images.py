"""Search Flickr for images of cameras that are missing photos.

Generates smart search queries (simplified names, multiple variants) and
searches Flickr camera collector groups + general CC search.

Usage:
    uv run python scripts/search_missing_images.py --dry-run     # preview queries
    uv run python scripts/search_missing_images.py               # search + download
    uv run python scripts/search_missing_images.py --resume      # skip already-attempted
    uv run python scripts/search_missing_images.py --brand Fujifilm  # one brand only
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")

from src.utils.data_io import MERGED_DIR

CAMERAS_JSON = MERGED_DIR / "cameras.json"
CAMERAS_IMAGES_REL = "data/images/cameras"
MIN_DELAY = 3.0  # seconds between Flickr requests
PROGRESS_PATH = Path("data/reports/flickr_search_progress.json")

# Flickr camera collector groups (photos OF cameras, not BY cameras)
CAMERA_GROUPS = [
    "55624923@N00",  # Old Film Cameras
    "94898401@N00",  # Camera Appreciation
    "54739042@N00",  # Your Camera Collection
]


def _sanitize_filename(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", name)
    s = re.sub(r"[\s_]+", "_", s).strip("_.")
    return s[:200] if s else "unknown"


def _generate_queries(name: str, manufacturer: str) -> list[str]:
    """Generate smart search query variants for a camera.

    Strips parenthetical aliases, tries different manufacturer prefixes,
    and generates both specific and broader queries.
    """
    queries = []

    # Strip parenthetical content for the base name
    base = re.sub(r"\s*\([^)]*\)", "", name).strip()

    # Strip manufacturer prefix from camera name if present
    model = base
    for pfx in sorted(
        {manufacturer, manufacturer.split()[0]} if manufacturer else set(),
        key=len,
        reverse=True,
    ):
        if model.lower().startswith(pfx.lower() + " "):
            model = model[len(pfx) :].strip()
            break
        if model.lower().startswith(pfx.lower()):
            model = model[len(pfx) :].strip()
            break

    # For most brands, the manufacturer + model is the best query
    if manufacturer:
        queries.append(f"{manufacturer} {model}")

    # Try with hyphens between letters and numbers (DL 200 -> DL-200)
    hyphenated = re.sub(r"(\D)\s+(\d)", r"\1-\2", model)
    if hyphenated != model and manufacturer:
        queries.append(f"{manufacturer} {hyphenated}")

    # Try shorter query (drop version suffixes like "II", "III", trailing words)
    short = re.sub(r"\s+(I{2,3}|IV|V|VI)$", "", model)
    short = re.sub(r"\s+(Date|Zoom|Wide|Tele|Super|Plus|Flash|MR|MRC|OP)$", "", short)
    if short != model and manufacturer:
        queries.append(f"{manufacturer} {short}")

    # For Fuji cameras specifically, try all brand variants
    if manufacturer in ("Fujifilm", "Fuji"):
        for brand in ("Fuji", "Fujifilm", "Fujica"):
            q = f"{brand} {model}"
            if q not in queries:
                queries.append(q)

    # Broader: just the full original name (no manufacturer double-up)
    if base not in queries:
        queries.append(base)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower not in seen:
            seen.add(q_lower)
            unique.append(q)
    return unique


def _flickr_search(query: str, group_id: str | None = None) -> list[str]:
    """Search Flickr and return staticflickr image URLs."""
    encoded = urllib.parse.quote(query)
    if group_id:
        gid = urllib.parse.quote(group_id)
        url = (
            f"https://www.flickr.com/search/"
            f"?text={encoded}&group_id={gid}"
        )
    else:
        url = (
            f"https://www.flickr.com/search/"
            f"?text={encoded}"
            f"&license=2%2C3%2C4%2C5%2C6%2C9"
            f"&sort=relevance"
        )

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    # Extract staticflickr image URLs
    imgs = re.findall(
        r"(https?://live\.staticflickr\.com/\d+/\d+_\w+_[a-z]\.jpg)", html
    )
    return imgs


def _search_camera(name: str, manufacturer: str) -> str | None:
    """Search Flickr for a camera image. Returns big image URL or None.

    Optimized order: general CC search first (wider pool, 1 request per query),
    then camera collector groups only for the first query (3 requests).
    Worst case: ~5 general + 3 group = 8 requests instead of ~16.
    """
    queries = _generate_queries(name, manufacturer)

    # Pass 1: Try general CC search for each query variant (fast, wide pool)
    for query in queries:
        time.sleep(MIN_DELAY)
        imgs = _flickr_search(query)
        if imgs:
            return re.sub(r"_[a-z]\.jpg$", "_b.jpg", imgs[0])

    # Pass 2: Try camera collector groups with first query only (better signal)
    if queries:
        for group_id in CAMERA_GROUPS:
            time.sleep(MIN_DELAY)
            imgs = _flickr_search(queries[0], group_id=group_id)
            if imgs:
                return re.sub(r"_[a-z]\.jpg$", "_b.jpg", imgs[0])

    return None


def _download_image(url: str, dest: Path) -> bool:
    """Download an image file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = resp.read()
        if len(data) < 1000:  # too small, probably an error page
            return False
        dest.write_bytes(data)
        return True
    except Exception:
        return False


def find_missing_cameras(cameras: list[dict], brand_filter: str | None = None) -> list[tuple[int, dict]]:
    """Find cameras without local images, optionally filtered by brand."""
    missing = []
    for idx, cam in enumerate(cameras):
        has_local = any(img.get("local_path") for img in cam.get("images", []))
        if has_local:
            continue
        if brand_filter:
            mfr = cam.get("manufacturer_normalized", "")
            if mfr.lower() != brand_filter.lower():
                continue
        missing.append((idx, cam))
    return missing


def main():
    parser = argparse.ArgumentParser(description="Search Flickr for missing camera images")
    parser.add_argument("--dry-run", action="store_true", help="Preview queries without searching")
    parser.add_argument("--resume", action="store_true", help="Skip cameras already attempted")
    parser.add_argument("--brand", type=str, help="Only search cameras from this brand")
    parser.add_argument("--limit", type=int, help="Max cameras to search")
    args = parser.parse_args()

    cameras = json.loads(CAMERAS_JSON.read_text())
    missing = find_missing_cameras(cameras, brand_filter=args.brand)

    print(f"Total cameras: {len(cameras)}")
    print(f"Missing images: {len(missing)}")
    if args.brand:
        print(f"Filtered to brand: {args.brand}")

    # Load progress for --resume
    attempted = set()
    if args.resume and PROGRESS_PATH.exists():
        progress = json.loads(PROGRESS_PATH.read_text())
        attempted = set(progress.get("attempted", []))
        print(f"Resuming: {len(attempted)} cameras already attempted")
        missing = [(idx, cam) for idx, cam in missing if cam["name"] not in attempted]
        print(f"Remaining: {len(missing)}")

    if args.limit:
        missing = missing[: args.limit]
        print(f"Limited to: {len(missing)}")

    if args.dry_run:
        print(f"\n[DRY RUN] Query preview for {len(missing)} cameras:\n")
        for _, cam in missing[:50]:
            mfr = cam.get("manufacturer_normalized", "?")
            queries = _generate_queries(cam["name"], mfr)
            print(f"  {cam['name']} ({mfr})")
            for q in queries:
                print(f"    -> {q}")
        if len(missing) > 50:
            print(f"  ... and {len(missing) - 50} more")
        return

    # Search and download
    found = 0
    not_found = 0
    errors = 0
    found_names = []

    print(f"\nSearching Flickr for {len(missing)} cameras...\n")

    for i, (cam_idx, cam) in enumerate(missing):
        name = cam["name"]
        mfr = cam.get("manufacturer_normalized", "")
        print(f"  [{i + 1}/{len(missing)}] {mfr} {name}...", end=" ", flush=True)

        try:
            img_url = _search_camera(name, mfr)
        except Exception as e:
            print(f"ERROR ({e})")
            errors += 1
            attempted.add(name)
            continue

        if not img_url:
            print("not found")
            not_found += 1
            attempted.add(name)
        else:
            # Build target path: Brand/Format/Model/main.jpg
            brand_dir = _sanitize_filename(mfr) if mfr else "unknown"
            model_dir = _sanitize_filename(name)
            ext = "jpg"
            local_rel = f"{CAMERAS_IMAGES_REL}/{brand_dir}/{model_dir}/main.{ext}"
            dest = Path(local_rel)

            if dest.exists():
                print(f"already exists at {local_rel}")
                # Just update cameras.json
                imgs = cam.get("images", [])
                if imgs:
                    imgs[0]["local_path"] = local_rel
                else:
                    cam["images"] = [
                        {"url": img_url, "source": "flickr_search", "license": "CC", "local_path": local_rel}
                    ]
                found += 1
                found_names.append(name)
            elif _download_image(img_url, dest):
                print(f"DOWNLOADED -> {local_rel}")
                # Update cameras.json entry
                imgs = cam.get("images", [])
                if imgs:
                    imgs[0]["url"] = img_url
                    imgs[0]["source"] = "flickr_search"
                    imgs[0]["license"] = "CC"
                    imgs[0]["local_path"] = local_rel
                else:
                    cam["images"] = [
                        {"url": img_url, "source": "flickr_search", "license": "CC", "local_path": local_rel}
                    ]
                found += 1
                found_names.append(name)
            else:
                print(f"download failed ({img_url})")
                errors += 1

            attempted.add(name)

        # Save progress every 25 cameras
        if (i + 1) % 25 == 0:
            CAMERAS_JSON.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
            PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
            PROGRESS_PATH.write_text(
                json.dumps({"attempted": sorted(attempted), "found": sorted(found_names)}, indent=2)
            )
            print(f"\n  -- Progress: {found} found, {not_found} not found, {errors} errors --\n")

    # Final save
    CAMERAS_JSON.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(
        json.dumps({"attempted": sorted(attempted), "found": sorted(found_names)}, indent=2)
    )

    print(f"\nDone!")
    print(f"  Found: {found}")
    print(f"  Not found: {not_found}")
    print(f"  Errors: {errors}")
    print(f"  New coverage: {found}/{len(missing)} ({found / len(missing) * 100:.1f}%)")


if __name__ == "__main__":
    main()
