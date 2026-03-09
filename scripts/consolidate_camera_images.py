"""Consolidate camera images: redistribute misplaced extras as new camera entries.

When camera records were merged, extras from collectiblend got combined — including
images of *related but different* models. This script:

1. Parses collectiblend image URLs to identify which extras belong to different models
2. Creates new camera entries for misplaced extras (with images + source refs)
3. Moves image files to correct model folders on disk
4. Runs hash-based duplicate detection
5. Cleans up orphan numbered files
6. Generates an HTML review sheet for non-collectiblend extras

Usage:
    uv run python scripts/consolidate_camera_images.py --dry-run
    uv run python scripts/consolidate_camera_images.py --execute
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import uuid
from pathlib import Path

sys.path.insert(0, ".")

from src.normalization.manufacturers import MANUFACTURER_COUNTRIES, normalize_manufacturer
from src.utils.data_io import MERGED_DIR

CAMERAS_FILE = MERGED_DIR / "cameras.json"
IMAGES_DIR = Path("data/images/cameras")
REPORTS_DIR = Path("data/reports")


def _sanitize(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', '_', name)
    s = re.sub(r'[\s_]+', '_', s).strip('_.')
    return s[:200] if s else 'unknown'


def _resolve_image_path(cam: dict) -> Path | None:
    brand = _sanitize(cam.get("manufacturer_normalized", ""))
    model = _sanitize(cam.get("name", ""))
    p = IMAGES_DIR / brand / model / "main.jpg"
    if p.exists():
        return p
    return None


def load_cameras() -> list[dict]:
    return json.loads(CAMERAS_FILE.read_text())


def save_cameras(cameras: list[dict]) -> None:
    CAMERAS_FILE.write_text(json.dumps(cameras, indent=2, ensure_ascii=False) + "\n")


def fix_local_paths(cameras: list[dict]) -> int:
    fixed = 0
    for cam in cameras:
        p = _resolve_image_path(cam)
        for img in cam.get("images", []):
            old_lp = img.get("local_path", "")
            if p:
                correct_lp = str(p)
                if old_lp != correct_lp:
                    img["local_path"] = correct_lp
                    fixed += 1
            elif old_lp:
                del img["local_path"]
                fixed += 1
            break
    return fixed


# =========================================================================
# Step 1a: Parse collectiblend URLs to identify misplaced extras
# =========================================================================

def _get_collectiblend_brand(cam: dict) -> str | None:
    """Get the collectiblend URL brand directory for this camera."""
    for s in cam.get("sources", []):
        if s.get("source") == "collectiblend" and s.get("source_url"):
            url = s["source_url"]
            parts = url.split("/Cameras/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
    return None


def _get_collectiblend_model(cam: dict) -> str | None:
    """Get the collectiblend page model name (from source URL)."""
    for s in cam.get("sources", []):
        if s.get("source") == "collectiblend" and s.get("source_url"):
            url = s["source_url"]
            return url.split("/")[-1].replace(".html", "")
    return None


# Some collectiblend brands use alternate prefixes in image filenames
# e.g., Asahi cameras may have Pentax-prefixed image URLs
_BRAND_PREFIX_ALIASES: dict[str, list[str]] = {
    "Asahi": ["Pentax"],
    "Zeiss-Ikon": ["Zeiss-Ikon-VEB"],
    "Zeiss-Ikon-VEB": ["Zeiss-Ikon"],
}


def _extract_model_from_image_url(url: str, brand_prefix: str) -> str | None:
    """Extract the model name from a collectiblend image URL.

    Image URL: https://collectiblend.com/Cameras/images/{brand_prefix}-{model}.jpg
    Returns the model part (e.g., 'Nikon-F-301').
    """
    fname = url.split("/images/")[-1].replace(".jpg", "")
    # Try primary brand prefix first
    prefix = brand_prefix + "-"
    if fname.startswith(prefix):
        return fname[len(prefix):]
    # Try aliases (e.g., Asahi -> Pentax)
    for alias in _BRAND_PREFIX_ALIASES.get(brand_prefix, []):
        alt_prefix = alias + "-"
        if fname.startswith(alt_prefix):
            return fname[len(alt_prefix):]
    return None


def _model_to_camera_name(model: str) -> str:
    """Convert collectiblend URL model name to human-readable camera name.

    'Nikon-F-301' -> 'Nikon F-301'
    'Instax-Mini-9' -> 'Instax Mini 9'

    Heuristic: hyphens between words are spaces, but preserve hyphens before
    numbers (e.g., F-301) or within established patterns.
    """
    # Replace hyphens with spaces
    name = model.replace("-", " ")
    # Re-join letter-number patterns that should have hyphens
    # e.g., "F 301" -> "F-301", "FE 2" -> "FE-2", "EF 1" -> "EF-1"
    name = re.sub(r'\b([A-Z]{1,3}) (\d)', r'\1-\2', name)
    # Also handle lowercase single letters before numbers
    name = re.sub(r'\b([a-z]) (\d)', r'\1-\2', name)
    return name


def classify_collectiblend_extras(cameras: list[dict]) -> dict:
    """Classify collectiblend extras as 'correct' or 'misplaced'.

    Returns dict with:
        - misplaced: list of (source_cam, image_entry, url_brand, extracted_model)
        - correct: list of (source_cam, image_entry)
        - stats: counts
    """
    misplaced = []
    correct = []

    for cam in cameras:
        url_brand = _get_collectiblend_brand(cam)
        own_model = _get_collectiblend_model(cam)
        if not url_brand or not own_model:
            continue

        imgs = cam.get("images", [])
        for img in imgs:
            if img.get("source") != "collectiblend":
                continue

            extracted = _extract_model_from_image_url(img["url"], url_brand)
            if not extracted:
                continue

            if extracted == own_model:
                correct.append((cam, img))
            else:
                misplaced.append((cam, img, url_brand, extracted))

    return {
        "misplaced": misplaced,
        "correct": correct,
        "stats": {
            "misplaced": len(misplaced),
            "correct": len(correct),
        }
    }


# =========================================================================
# Step 1b: Create new camera entries for misplaced extras
# =========================================================================

def _build_name_index(cameras: list[dict]) -> dict[str, dict]:
    """Build lookup: normalized 'manufacturer|name' -> camera dict."""
    index = {}
    for cam in cameras:
        mfr = (cam.get("manufacturer_normalized") or "").lower().strip()
        name = cam.get("name", "").lower().strip()
        key = f"{mfr}|{name}"
        index[key] = cam
    return index


def create_new_cameras(
    misplaced: list[tuple[dict, dict, str, str]],
    existing_index: dict[str, dict],
) -> tuple[list[dict], list[tuple[dict, dict, str]], int]:
    """Create new Camera entries from misplaced extras.

    Returns:
        - new_cameras: list of new camera dicts
        - matched_existing: list of (existing_cam, image_entry, url_brand)
          for extras that match an existing camera
        - skipped: count of skipped (duplicate new entries for same model)
    """
    new_cameras = []
    matched_existing = []
    seen_models = {}  # (manufacturer, model) -> new_cam to avoid duplicates
    skipped = 0

    for source_cam, img, url_brand, extracted_model in misplaced:
        mfr = source_cam.get("manufacturer_normalized", "")
        mfr_country = source_cam.get("manufacturer_country", "")
        manufacturer_raw = source_cam.get("manufacturer", mfr)

        camera_name = _model_to_camera_name(extracted_model)

        # Check if this model already exists in the database
        check_key = f"{mfr.lower().strip()}|{camera_name.lower().strip()}"
        if check_key in existing_index:
            matched_existing.append((existing_index[check_key], img, url_brand))
            continue

        # Check if we've already created a new entry for this model
        dedup_key = (mfr.lower(), camera_name.lower())
        if dedup_key in seen_models:
            # Add image to existing new camera
            existing_new = seen_models[dedup_key]
            existing_urls = {i["url"] for i in existing_new["images"]}
            if img["url"] not in existing_urls:
                existing_new["images"].append(dict(img))
            skipped += 1
            continue

        # Construct collectiblend page URL for source reference
        source_url = f"https://collectiblend.com/Cameras/{url_brand}/{extracted_model}.html"

        new_cam = {
            "id": str(uuid.uuid4()),
            "name": camera_name,
            "manufacturer": manufacturer_raw,
            "manufacturer_normalized": mfr,
            "manufacturer_country": mfr_country or MANUFACTURER_COUNTRIES.get(mfr),
            "images": [dict(img)],
            "sources": [{
                "source": "collectiblend",
                "source_url": source_url,
            }],
        }

        new_cameras.append(new_cam)
        seen_models[dedup_key] = new_cam
        existing_index[check_key] = new_cam

    return new_cameras, matched_existing, skipped


# =========================================================================
# Step 1c: Hash-based cross-model duplicate detection
# =========================================================================

_DUPE_SUSPECT_SOURCES = {"flickr_scrape", "flickr_search", "commons_search", "chinesecamera"}


def _get_source(cam: dict) -> str:
    for img in cam.get("images", []):
        return img.get("source", "unknown")
    return "unknown"


def build_hash_index(cameras: list[dict]) -> dict[str, list[tuple[dict, Path]]]:
    """Map MD5 hash -> list of (camera, image_path) tuples."""
    hash_map: dict[str, list[tuple[dict, Path]]] = {}
    for cam in cameras:
        p = _resolve_image_path(cam)
        if not p:
            continue
        try:
            h = hashlib.md5(p.read_bytes()).hexdigest()
            hash_map.setdefault(h, []).append((cam, p))
        except Exception:
            pass
    return hash_map


def find_duplicates(hash_map: dict[str, list[tuple[dict, Path]]]) -> dict[str, tuple[Path, str]]:
    """Find cross-brand and suspect same-brand duplicates."""
    flagged: dict[str, tuple[Path, str]] = {}

    for h, entries in hash_map.items():
        if len(entries) < 2:
            continue
        brands = {e[0].get("manufacturer_normalized", "") for e in entries}
        names = {e[0]["name"] for e in entries}

        if len(brands) > 1:
            # Cross-brand duplicate — flag all
            for cam, p in entries:
                flagged[cam["id"]] = (p, "cross-brand duplicate")
        elif len(names) > 1:
            # Same-brand, different models
            sources = {_get_source(e[0]) for e in entries}
            is_suspect = bool(sources & _DUPE_SUSPECT_SOURCES)
            is_large = len(entries) > 2
            if is_suspect or is_large:
                for cam, p in entries:
                    flagged[cam["id"]] = (p, "same-brand duplicate")

    return flagged


# =========================================================================
# Step 1d: Move images on disk
# =========================================================================

def move_image_to_model(
    img: dict,
    source_cam: dict,
    target_model_name: str,
    dry_run: bool,
) -> str | None:
    """Move an extra image file to a new model's main.jpg folder.

    Returns the new local_path if successful, None otherwise.
    """
    old_lp = img.get("local_path", "")
    if not old_lp:
        return None

    old_path = Path(old_lp)
    if not old_path.exists():
        return None

    brand = _sanitize(source_cam.get("manufacturer_normalized", ""))
    model = _sanitize(target_model_name)
    new_dir = IMAGES_DIR / brand / model
    new_path = new_dir / "main.jpg"

    if new_path.exists():
        # Target already has an image — don't overwrite
        return None

    if not dry_run:
        new_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_path), str(new_path))

    return str(new_path)


# =========================================================================
# Step 1d: Clean up orphan numbered files
# =========================================================================

def find_orphan_numbered_files() -> list[Path]:
    orphans = []
    for brand_dir in sorted(IMAGES_DIR.iterdir()):
        if not brand_dir.is_dir() or brand_dir.name.startswith("_"):
            continue
        for model_dir in sorted(brand_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            for f in sorted(model_dir.iterdir()):
                if f.is_file() and f.name not in ("main.jpg", "main.png", ".DS_Store"):
                    orphans.append(f)
    return orphans


def cleanup_orphans_and_empty_dirs(dry_run: bool) -> tuple[int, int]:
    """Delete orphan numbered files and empty directories. Returns (files, dirs)."""
    orphans = find_orphan_numbered_files()

    if not dry_run:
        for f in orphans:
            f.unlink()

    # Remove .DS_Store files
    for f in IMAGES_DIR.rglob(".DS_Store"):
        if not dry_run:
            f.unlink()

    # Remove empty directories bottom-up
    empty_count = 0
    for d in sorted(IMAGES_DIR.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            if not dry_run:
                d.rmdir()
            empty_count += 1

    return len(orphans), empty_count


# =========================================================================
# Step 1e: Generate review contact sheet for non-collectiblend extras
# =========================================================================

def generate_extras_review_sheet(cameras: list[dict]) -> int:
    """Generate HTML contact sheet for non-collectiblend extra images.

    Shows each extra alongside the camera name and main image for visual review.
    Returns the number of extras included.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORTS_DIR / "extra_images_review.html"

    # Collect non-collectiblend extras
    entries = []  # (cam_name, brand, source, main_path, extra_path, extra_url)
    for cam in cameras:
        imgs = cam.get("images", [])
        if len(imgs) <= 1:
            continue

        main_path = _resolve_image_path(cam)
        brand = cam.get("manufacturer_normalized", "?")
        name = cam.get("name", "?")

        for img in imgs[1:]:
            src = img.get("source", "unknown")
            if src == "collectiblend":
                continue
            lp = img.get("local_path", "")
            if lp and Path(lp).exists():
                entries.append((name, brand, src, str(main_path) if main_path else "", lp, img.get("url", "")))

    if not entries:
        print("  No non-collectiblend extras to review.")
        return 0

    # Group by source -> brand
    by_source: dict[str, dict[str, list]] = {}
    for name, brand, src, main_p, extra_p, url in entries:
        by_source.setdefault(src, {}).setdefault(brand, []).append((name, main_p, extra_p, url))

    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Extra Images Review</title>
<style>
body { font-family: -apple-system, sans-serif; background: #111; color: #eee; margin: 20px; }
h1 { color: #fff; }
h2 { color: #aaf; margin-top: 30px; border-bottom: 1px solid #333; padding-bottom: 5px; }
h3 { color: #8a8; margin-top: 15px; }
.grid { display: flex; flex-wrap: wrap; gap: 12px; }
.card { background: #222; border-radius: 4px; padding: 6px; width: 380px; }
.card .pair { display: flex; gap: 6px; }
.card img { width: 180px; height: 130px; object-fit: cover; border-radius: 2px; cursor: pointer; }
.card img:hover { outline: 2px solid #ff0; }
.card .label { font-size: 11px; color: #aaa; margin-top: 4px; word-break: break-all; }
.card .main-label { color: #6a6; font-size: 10px; }
.card .extra-label { color: #a66; font-size: 10px; }
.stats { color: #888; font-size: 14px; }
</style>
</head>
<body>
<h1>Extra Images Review</h1>
<p class="stats">Each card shows main image (left, green) and extra image (right, red). Review if the extra matches the camera.</p>
"""

    source_order = ["flickr_scrape", "chinesecamera", "lomography_shop", "commons_search"]
    for src in source_order:
        if src not in by_source:
            continue
        brands = by_source[src]
        total = sum(len(v) for v in brands.values())
        html += f'<h2>{src} ({total} extras)</h2>\n'

        for brand in sorted(brands.keys()):
            items = brands[brand]
            html += f'<h3>{brand} ({len(items)})</h3>\n<div class="grid">\n'
            for name, main_p, extra_p, url in sorted(items):
                main_img = f'<img src="../../{main_p}" loading="lazy">' if main_p else '<div style="width:180px;height:130px;background:#333;"></div>'
                html += f"""<div class="card">
<div class="pair">
<div>{main_img}<div class="main-label">main</div></div>
<div><a href="../../{extra_p}" target="_blank"><img src="../../{extra_p}" loading="lazy"></a><div class="extra-label">extra</div></div>
</div>
<div class="label">{name}</div>
</div>
"""
            html += '</div>\n'

    html += "</body></html>"
    output.write_text(html)
    return len(entries)


# =========================================================================
# Main
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Consolidate camera images: redistribute misplaced extras")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without modifying anything")
    group.add_argument("--execute", action="store_true", help="Apply all changes")
    args = parser.parse_args()

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "EXECUTE"
    print(f"=== Camera Image Consolidation [{mode}] ===\n")

    cameras = load_cameras()
    print(f"Loaded {len(cameras)} cameras")
    with_images = sum(1 for c in cameras if _resolve_image_path(c))
    print(f"  With images on disk: {with_images}")

    # ─── Step 1a: Classify collectiblend extras ───
    print("\n" + "=" * 70)
    print("Step 1a: Classify collectiblend extras")
    print("=" * 70)

    result = classify_collectiblend_extras(cameras)
    misplaced = result["misplaced"]
    print(f"  Collectiblend extras correctly placed: {result['stats']['correct']}")
    print(f"  Collectiblend extras MISPLACED: {result['stats']['misplaced']}")

    # Show some examples
    if misplaced:
        print("\n  Examples of misplaced extras:")
        seen = set()
        for source_cam, img, url_brand, extracted_model in misplaced[:10]:
            cam_name = _model_to_camera_name(extracted_model)
            if cam_name not in seen:
                print(f"    {source_cam['name']:35} has image of: {cam_name}")
                seen.add(cam_name)

    # ─── Step 1b: Create new camera entries ───
    print("\n" + "=" * 70)
    print("Step 1b: Create new camera entries from misplaced extras")
    print("=" * 70)

    existing_index = _build_name_index(cameras)
    new_cameras, matched_existing, skipped = create_new_cameras(misplaced, existing_index)

    print(f"  New camera entries to create: {len(new_cameras)}")
    print(f"  Matched existing cameras: {len(matched_existing)}")
    print(f"  Deduplicated (same model from multiple cameras): {skipped}")

    # Count how many new cameras have downloadable images
    new_with_local = sum(1 for c in new_cameras
                        if any(i.get("local_path") and Path(i["local_path"]).exists()
                              for i in c["images"]))
    print(f"  New cameras with downloaded images: {new_with_local}")

    if new_cameras:
        print("\n  Sample new cameras:")
        for c in new_cameras[:15]:
            has_img = "✓" if any(i.get("local_path") and Path(i["local_path"]).exists() for i in c["images"]) else " "
            print(f"    [{has_img}] {c['manufacturer_normalized']:15} {c['name']}")
        if len(new_cameras) > 15:
            print(f"    ... and {len(new_cameras) - 15} more")

    # ─── Step 1b (cont): Move images on disk ───
    print("\n" + "=" * 70)
    print("Step 1b (cont): Move images to correct model folders")
    print("=" * 70)

    moved = 0
    move_failed = 0
    for new_cam in new_cameras:
        for img in new_cam["images"]:
            old_lp = img.get("local_path", "")
            if not old_lp or not Path(old_lp).exists():
                continue

            new_lp = move_image_to_model(img, new_cam, new_cam["name"], dry_run)
            if new_lp:
                if not dry_run:
                    img["local_path"] = new_lp
                moved += 1
            else:
                move_failed += 1

    # Also handle matched_existing — move image if target has no image
    matched_moved = 0
    for existing_cam, img, url_brand in matched_existing:
        existing_path = _resolve_image_path(existing_cam)
        if existing_path:
            continue  # Already has an image

        old_lp = img.get("local_path", "")
        if not old_lp or not Path(old_lp).exists():
            continue

        new_lp = move_image_to_model(img, existing_cam, existing_cam["name"], dry_run)
        if new_lp:
            if not dry_run:
                # Add image to existing camera
                existing_cam["images"].insert(0, {
                    "url": img["url"],
                    "source": img.get("source", "collectiblend"),
                    "local_path": new_lp,
                    "is_hosted": False,
                })
            matched_moved += 1

    print(f"  Images moved to new model folders: {moved}")
    print(f"  Images moved to existing cameras: {matched_moved}")
    print(f"  Move failed (target already has image): {move_failed}")

    # ─── Remove misplaced extras from source cameras ───
    print("\n" + "=" * 70)
    print("Step 1b (cont): Remove misplaced extras from source cameras")
    print("=" * 70)

    # Build set of image URLs to remove from their source cameras
    urls_to_remove = set()
    for _, img, _, _ in misplaced:
        urls_to_remove.add(img["url"])

    removed_count = 0
    if not dry_run:
        for cam in cameras:
            orig_len = len(cam.get("images", []))
            cam["images"] = [
                i for i in cam.get("images", [])
                if i["url"] not in urls_to_remove
            ]
            removed_count += orig_len - len(cam["images"])
    else:
        removed_count = len(urls_to_remove)

    print(f"  Image entries removed from source cameras: {removed_count}")

    # ─── Append new cameras ───
    if not dry_run:
        cameras.extend(new_cameras)
    print(f"\n  Total cameras after adding new entries: {len(cameras) + (len(new_cameras) if dry_run else 0)}")

    # ─── Step 1c: Hash-based duplicate detection ───
    print("\n" + "=" * 70)
    print("Step 1c: Hash-based duplicate detection")
    print("=" * 70)

    if not dry_run:
        hash_map = build_hash_index(cameras)
        dupes = find_duplicates(hash_map)

        cross_brand = sum(1 for _, (_, r) in dupes.items() if r == "cross-brand duplicate")
        same_brand = sum(1 for _, (_, r) in dupes.items() if r == "same-brand duplicate")
        print(f"  Cross-brand duplicates: {cross_brand}")
        print(f"  Same-brand duplicates: {same_brand}")
        print(f"  Total flagged: {len(dupes)}")

        if dupes:
            print("\n  Flagged duplicates (not auto-removing, run audit_camera_images.py --fix):")
            shown = 0
            for cam_id, (path, reason) in list(dupes.items())[:20]:
                cam = next((c for c in cameras if c.get("id") == cam_id), None)
                if cam:
                    print(f"    {cam['manufacturer_normalized']:15} {cam['name']:35} [{reason}]")
                    shown += 1
            if len(dupes) > 20:
                print(f"    ... and {len(dupes) - 20} more")
    else:
        print("  (skipped in dry-run mode)")

    # ─── Step 1d: Clean up orphan files ───
    print("\n" + "=" * 70)
    print("Step 1d: Clean up orphan numbered files")
    print("=" * 70)

    orphans = find_orphan_numbered_files()
    print(f"  Orphan numbered files on disk: {len(orphans)}")

    if orphans:
        for f in orphans[:10]:
            print(f"    {f.relative_to(IMAGES_DIR)}")
        if len(orphans) > 10:
            print(f"    ... and {len(orphans) - 10} more")

    if not dry_run and orphans:
        files_deleted, dirs_removed = cleanup_orphans_and_empty_dirs(dry_run=False)
        print(f"  Deleted {files_deleted} orphan files, removed {dirs_removed} empty directories")
    elif dry_run and orphans:
        print(f"  Would delete {len(orphans)} orphan files")

    # ─── Step 1e: Generate review sheet for non-collectiblend extras ───
    print("\n" + "=" * 70)
    print("Step 1e: Generate review sheet for non-collectiblend extras")
    print("=" * 70)

    extras_count = generate_extras_review_sheet(cameras if not dry_run else cameras)
    if extras_count:
        print(f"  Generated review sheet with {extras_count} extras")
        print(f"  Output: {REPORTS_DIR / 'extra_images_review.html'}")

    # ─── Step 1f: Fix local paths and save ───
    print("\n" + "=" * 70)
    print("Step 1f: Fix local paths and save")
    print("=" * 70)

    if not dry_run:
        fixed = fix_local_paths(cameras)
        print(f"  Fixed {fixed} local_path values")

        save_cameras(cameras)
        print(f"  Saved cameras.json")

    # ─── Summary ───
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total = len(cameras) + (len(new_cameras) if dry_run else 0)
    final_with_images = sum(1 for c in cameras if _resolve_image_path(c))
    if dry_run:
        final_with_images += new_with_local

    print(f"  Total cameras: {total}")
    print(f"  With images: {final_with_images}")
    print(f"  New cameras created: {len(new_cameras)}")
    print(f"  Images relocated: {moved}")
    print(f"  Images donated to existing cameras: {matched_moved}")
    print(f"  Orphan files {'to delete' if dry_run else 'deleted'}: {len(orphans)}")

    if dry_run:
        print(f"\n[DRY RUN] No changes made. Run with --execute to apply.")


if __name__ == "__main__":
    main()
