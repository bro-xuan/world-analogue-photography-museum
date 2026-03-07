"""Audit camera images for quality issues and flag bad ones as missing.

Scans the filesystem for actual images and cross-references with cameras.json.
The local_path values in cameras.json are often stale (include film_format subdir),
so this script resolves images via the brand/model folder convention on disk.

Checks:
1. Cross-brand duplicates (same image file for cameras from different manufacturers)
2. Same-brand duplicates from non-collectiblend sources (flickr often returns one
   generic photo for many models — e.g. Bell & Howell 57 models sharing one image)
3. Unreliable source images (flickr_search, commons_search) — high false-positive rate
4. Tiny/broken files (< 5KB or < 100px dimension)

After fixing, also repairs stale local_path values in cameras.json to match the
actual filesystem layout (brand/model/main.jpg without film_format subdir).

Usage:
    uv run python scripts/audit_camera_images.py           # Report only
    uv run python scripts/audit_camera_images.py --fix     # Remove bad images + fix paths
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, ".")

from src.utils.data_io import MERGED_DIR

CAMERAS_FILE = MERGED_DIR / "cameras.json"
IMAGES_DIR = Path("data/images/cameras")

# Same-brand dupes from collectiblend are often legit variants (A21 vs Argus 21).
# Only flag same-brand dupes from these unreliable scrape/search sources.
_DUPE_SUSPECT_SOURCES = {"flickr_scrape", "flickr_search", "commons_search", "chinesecamera"}


def _sanitize(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', '_', name)
    s = re.sub(r'[\s_]+', '_', s).strip('_.')
    return s[:200] if s else 'unknown'


def _resolve_image_path(cam: dict) -> Path | None:
    """Find the actual main.jpg on disk for a camera."""
    brand = _sanitize(cam.get("manufacturer_normalized", ""))
    model = _sanitize(cam.get("name", ""))
    p = IMAGES_DIR / brand / model / "main.jpg"
    if p.exists():
        return p
    ff = cam.get("film_format", "")
    if ff:
        p2 = IMAGES_DIR / brand / _sanitize(ff) / model / "main.jpg"
        if p2.exists():
            return p2
    return None


def _get_source(cam: dict) -> str:
    for img in cam.get("images", []):
        return img.get("source", "unknown")
    return "unknown"


def load_cameras() -> list[dict]:
    return json.loads(CAMERAS_FILE.read_text())


def save_cameras(cameras: list[dict]) -> None:
    CAMERAS_FILE.write_text(json.dumps(cameras, indent=2, ensure_ascii=False) + "\n")


def build_hash_index(cameras: list[dict]) -> dict[str, list[tuple[dict, Path]]]:
    """Map MD5 hash -> list of (camera, image_path) tuples."""
    hash_map: dict[str, list[tuple[dict, Path]]] = {}
    for cam in cameras:
        p = _resolve_image_path(cam)
        if not p:
            continue
        h = hashlib.md5(p.read_bytes()).hexdigest()
        hash_map.setdefault(h, []).append((cam, p))
    return hash_map


def clear_image(cam: dict, image_path: Path | None = None) -> bool:
    """Remove image file from disk and clear local_path in data."""
    p = image_path or _resolve_image_path(cam)
    if p and p.exists():
        p.unlink()
        parent = p.parent
        try:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except Exception:
            pass

    changed = False
    for img in cam.get("images", []):
        if "local_path" in img:
            del img["local_path"]
            changed = True
    return changed


def fix_local_paths(cameras: list[dict]) -> int:
    """Update local_path to match actual filesystem location. Returns count fixed."""
    fixed = 0
    for cam in cameras:
        for img in cam.get("images", []):
            p = _resolve_image_path(cam)
            old_lp = img.get("local_path", "")
            if p:
                correct_lp = str(p)
                if old_lp != correct_lp:
                    img["local_path"] = correct_lp
                    fixed += 1
            elif old_lp:
                # local_path set but file doesn't exist — clear it
                del img["local_path"]
                fixed += 1
            break  # only first image
    return fixed


def main():
    parser = argparse.ArgumentParser(description="Audit camera image quality")
    parser.add_argument("--fix", action="store_true", help="Remove all flagged bad images and fix paths")
    args = parser.parse_args()

    cameras = load_cameras()

    cams_with_images = []
    for cam in cameras:
        p = _resolve_image_path(cam)
        if p:
            cams_with_images.append((cam, p))

    print(f"Loaded {len(cameras)} cameras, {len(cams_with_images)} with images on disk\n")

    hash_map = build_hash_index(cameras)

    # Collect all IDs to fix, with reason and path
    flagged: dict[str, tuple[Path, str]] = {}  # cam_id -> (path, reason)

    # =========================================================
    # 1. CROSS-BRAND DUPLICATES (all flagged)
    # =========================================================
    print("=" * 70)
    print("1. CROSS-BRAND DUPLICATES (same file, different brands)")
    print("=" * 70)

    cross_count = 0
    cross_groups = 0
    for h, entries in hash_map.items():
        if len(entries) < 2:
            continue
        brands = {e[0].get("manufacturer_normalized", "") for e in entries}
        if len(brands) <= 1:
            continue
        cross_groups += 1
        brand_list = sorted(brands)
        print(f"\n  Hash {h[:12]} — {', '.join(brand_list)}:")
        for cam, p in entries:
            print(f"    {cam['manufacturer_normalized']:15} {cam['name']:35} [{_get_source(cam)}]")
            flagged[cam["id"]] = (p, "cross-brand duplicate")
            cross_count += 1

    print(f"\n  Flagged: {cross_count} cameras in {cross_groups} groups\n")

    # =========================================================
    # 2. SAME-BRAND DUPLICATES (non-collectiblend, or large groups)
    # =========================================================
    print("=" * 70)
    print("2. SAME-BRAND DUPLICATES (non-collectiblend sources or group > 2)")
    print("=" * 70)

    same_count = 0
    same_groups = 0
    same_skipped = 0
    for h, entries in hash_map.items():
        if len(entries) < 2:
            continue
        brands = {e[0].get("manufacturer_normalized", "") for e in entries}
        names = {e[0]["name"] for e in entries}
        if len(brands) != 1 or len(names) <= 1:
            continue

        sources = {_get_source(e[0]) for e in entries}
        is_suspect_source = bool(sources & _DUPE_SUSPECT_SOURCES)
        is_large_group = len(entries) > 2

        if not is_suspect_source and not is_large_group:
            same_skipped += len(entries)
            continue

        same_groups += 1
        brand = entries[0][0].get("manufacturer_normalized", "?")
        print(f"\n  Hash {h[:12]} — {brand} ({len(entries)} models):")
        for cam, p in entries:
            src = _get_source(cam)
            print(f"    {cam['name']:40} [{src}]")
            flagged[cam["id"]] = (p, "same-brand duplicate")
            same_count += 1

    print(f"\n  Flagged: {same_count} cameras in {same_groups} groups")
    print(f"  Skipped: {same_skipped} cameras (collectiblend pairs, likely legit variants)\n")

    # =========================================================
    # 3. UNRELIABLE SOURCES (flickr_search, commons_search)
    # =========================================================
    print("=" * 70)
    print("3. UNRELIABLE SOURCE IMAGES (flickr_search / commons_search)")
    print("=" * 70)

    unreliable_count = 0
    by_source: dict[str, list[tuple[dict, Path]]] = {}
    for cam, p in cams_with_images:
        src = _get_source(cam)
        if src in ("flickr_search", "commons_search"):
            by_source.setdefault(src, []).append((cam, p))
            if cam["id"] not in flagged:  # avoid double-counting
                flagged[cam["id"]] = (p, f"unreliable source ({src})")
                unreliable_count += 1

    for src, entries in sorted(by_source.items()):
        print(f"\n  {src} ({len(entries)} cameras):")
        for cam, p in entries[:15]:
            print(f"    {cam['manufacturer_normalized']:15} {cam['name']}")
        if len(entries) > 15:
            print(f"    ... and {len(entries) - 15} more")

    print(f"\n  Flagged (new): {unreliable_count} cameras\n")

    # =========================================================
    # 4. TINY / BROKEN FILES
    # =========================================================
    print("=" * 70)
    print("4. TINY / BROKEN FILES (< 5KB or < 100px)")
    print("=" * 70)

    tiny_count = 0
    for cam, p in cams_with_images:
        try:
            size = p.stat().st_size
            if size < 5000:
                if cam["id"] not in flagged:
                    flagged[cam["id"]] = (p, "tiny file")
                    tiny_count += 1
                print(f"  {cam['manufacturer_normalized']:15} {cam['name']:35} {size:>6}B")
                continue
            img = Image.open(p)
            w, h = img.size
            if w < 100 or h < 100:
                if cam["id"] not in flagged:
                    flagged[cam["id"]] = (p, "tiny dimensions")
                    tiny_count += 1
                print(f"  {cam['manufacturer_normalized']:15} {cam['name']:35} {w}x{h}")
        except Exception as e:
            if cam["id"] not in flagged:
                flagged[cam["id"]] = (p, "broken file")
                tiny_count += 1
            print(f"  {cam['manufacturer_normalized']:15} {cam['name']:35} BROKEN: {e}")

    print(f"\n  Flagged (new): {tiny_count} cameras\n")

    # =========================================================
    # 5. STALE LOCAL_PATHS
    # =========================================================
    print("=" * 70)
    print("5. STALE LOCAL_PATHS (path in JSON doesn't match filesystem)")
    print("=" * 70)

    stale = 0
    missing_on_disk = 0
    for cam in cameras:
        if cam["id"] in flagged:
            continue  # will be cleared anyway
        for img in cam.get("images", []):
            lp = img.get("local_path", "")
            p = _resolve_image_path(cam)
            if p and lp != str(p):
                stale += 1
            elif lp and not p:
                missing_on_disk += 1
            break

    print(f"  Stale paths (will be corrected): {stale}")
    print(f"  Missing on disk (will clear path): {missing_on_disk}\n")

    # =========================================================
    # SUMMARY
    # =========================================================
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Images to remove:          {len(flagged):>5}")
    print(f"    Cross-brand duplicates:  {cross_count:>5}")
    print(f"    Same-brand duplicates:   {same_count:>5}")
    print(f"    Unreliable sources:      {unreliable_count:>5}  (not already flagged above)")
    print(f"    Tiny/broken:             {tiny_count:>5}  (not already flagged above)")
    print(f"  Stale paths to fix:        {stale:>5}")
    print(f"  Missing paths to clear:    {missing_on_disk:>5}")
    print()

    if not args.fix:
        print("Run with --fix to apply all fixes.")
        return

    # =========================================================
    # APPLY FIXES
    # =========================================================
    print("Applying fixes...")

    # Step 1: Remove flagged images
    removed = 0
    for cam in cameras:
        if cam["id"] in flagged:
            image_path = flagged[cam["id"]][0]
            clear_image(cam, image_path)
            removed += 1
    print(f"  Removed {removed} bad images from disk + cleared local_path")

    # Step 2: Fix stale local_paths for remaining good images
    fixed = fix_local_paths(cameras)
    print(f"  Fixed {fixed} stale local_path values")

    # Step 3: Save
    save_cameras(cameras)

    # Count final state
    final_with_images = sum(1 for c in cameras if _resolve_image_path(c))
    final_no_images = len(cameras) - final_with_images
    print(f"\nDone. cameras.json saved.")
    print(f"  Cameras with valid images: {final_with_images}")
    print(f"  Cameras needing images:    {final_no_images}")


if __name__ == "__main__":
    main()
