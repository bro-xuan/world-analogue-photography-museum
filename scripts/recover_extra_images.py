"""Recover extra camera images with validation.

Re-downloads images from extra URLs in cameras.json (entries beyond the first),
then validates them to reject duplicates and contamination.

Validation checks:
1. Cross-model duplicate — MD5 matches a DIFFERENT camera's main.jpg → delete
2. Same-model duplicate — MD5 matches THIS camera's main.jpg → delete
3. Mass duplicate — same MD5 in >3 cameras as extra → brand gallery image → delete
4. Tiny file — <5KB → broken/placeholder → delete

Usage:
    uv run python scripts/recover_extra_images.py --dry-run    # Preview what would be downloaded
    uv run python scripts/recover_extra_images.py --execute     # Download and validate
"""

import argparse
import asyncio
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, ".")

from src.utils.data_io import MERGED_DIR
from src.utils.http import RateLimitedClient

CAMERAS_IMAGES = Path("data/images/cameras")
CAMERAS_JSON = MERGED_DIR / "cameras.json"

MIN_FILE_SIZE = 5 * 1024  # 5KB — below this is broken/placeholder
MASS_DUPE_THRESHOLD = 3  # same hash in >3 cameras = brand gallery image


def _sanitize_filename(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", name)
    s = re.sub(r"[\s_]+", "_", s).strip("_.")
    return s[:200] if s else "unknown"


def _ext_from_url(url: str) -> str:
    path = url.split("?")[0].split("#")[0]
    match = re.search(r"\.(\w{2,5})$", path)
    if match:
        ext = match.group(1).lower()
        if ext in ("jpg", "jpeg", "png", "gif", "webp", "tif", "tiff"):
            return ext
    return "jpg"


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def build_main_md5_index() -> dict[str, list[str]]:
    """Build MD5 → [relative_path, ...] index of all existing main.* files."""
    index: dict[str, list[str]] = {}
    for brand_dir in CAMERAS_IMAGES.iterdir():
        if not brand_dir.is_dir() or brand_dir.name.startswith("_"):
            continue
        for model_dir in brand_dir.iterdir():
            if not model_dir.is_dir():
                continue
            for f in model_dir.iterdir():
                if f.is_file() and f.name.startswith("main"):
                    h = _md5(f)
                    index.setdefault(h, []).append(str(f))
    return index


def find_extra_urls(cameras: list[dict]) -> list[tuple[int, int, dict, dict]]:
    """Find all extra image entries (index > 0) that have URLs.

    Returns list of (camera_idx, img_idx, camera, img_entry).
    """
    extras = []
    for cam_idx, cam in enumerate(cameras):
        images = cam.get("images", [])
        if len(images) <= 1:
            continue
        for img_idx, img in enumerate(images[1:], start=1):
            url = img.get("url", "")
            if url and "/icons/" not in url:
                extras.append((cam_idx, img_idx, cam, img))
    return extras


def dry_run_report(cameras: list[dict]) -> None:
    """Show what would be downloaded without downloading."""
    extras = find_extra_urls(cameras)
    print(f"\n  Extra image URLs to download: {len(extras)}")

    # By source
    source_counts: Counter[str] = Counter()
    for _, _, _, img in extras:
        source_counts[img.get("source", "unknown")] += 1
    print("  By source:")
    for src, cnt in source_counts.most_common():
        print(f"    {src}: {cnt}")

    # By camera count
    cam_counts: Counter[int] = Counter()
    for cam in cameras:
        n = len([img for img in cam.get("images", [])[1:] if img.get("url")])
        if n > 0:
            cam_counts[n] += 1
    print("  Cameras by extra-image count:")
    for n in sorted(cam_counts):
        print(f"    {n} extra: {cam_counts[n]} cameras")

    # Show a few examples
    print("\n  Sample cameras with extras:")
    shown = 0
    for cam in cameras:
        images = cam.get("images", [])
        if len(images) <= 1:
            continue
        extra_urls = [img for img in images[1:] if img.get("url")]
        if not extra_urls:
            continue
        mfr = cam.get("manufacturer_normalized", "?")
        print(f"    {mfr} / {cam['name']}: {len(extra_urls)} extra URLs ({extra_urls[0].get('source', '?')})")
        shown += 1
        if shown >= 10:
            break


async def download_and_validate(cameras: list[dict]) -> dict:
    """Download extra images, validate, and clean up bad ones."""
    extras = find_extra_urls(cameras)
    main_md5_index = build_main_md5_index()
    print(f"  Main file MD5 index: {sum(len(v) for v in main_md5_index.values())} files, "
          f"{len(main_md5_index)} unique hashes")
    print(f"  Extra URLs to download: {len(extras)}")

    stats = {
        "downloaded": 0,
        "failed": 0,
        "cross_model_dupe": 0,
        "same_model_dupe": 0,
        "tiny": 0,
        "kept": 0,
    }

    # Track MD5 of each downloaded extra file for mass-dupe detection
    # extra_md5s: hash → list of dest paths
    extra_md5s: dict[str, list[Path]] = {}
    # Map dest path → (cam_idx, img_idx) for JSON updates
    path_to_entry: dict[Path, tuple[int, int]] = {}

    async with RateLimitedClient(min_delay=0.5, verify_ssl=False) as client:
        for i, (cam_idx, img_idx, cam, img) in enumerate(extras):
            url = img["url"]
            mfr = cam.get("manufacturer_normalized", "Unknown")
            name = cam["name"]
            safe_mfr = _sanitize_filename(mfr)
            safe_name = _sanitize_filename(name)
            ext = _ext_from_url(url)
            filename = f"{img_idx + 1}.{ext}"
            dest = CAMERAS_IMAGES / safe_mfr / safe_name / filename

            # Skip if already exists on disk
            if dest.exists():
                stats["downloaded"] += 1
                h = _md5(dest)
                extra_md5s.setdefault(h, []).append(dest)
                path_to_entry[dest] = (cam_idx, img_idx)
                continue

            success = await client.download_file(url, dest)

            if not success:
                stats["failed"] += 1
                img["local_path"] = None
                if (i + 1) % 200 == 0:
                    print(f"  [{i+1}/{len(extras)}] downloaded={stats['downloaded']} "
                          f"failed={stats['failed']}", flush=True)
                continue

            stats["downloaded"] += 1

            # --- Immediate validation ---

            # Check file size
            if dest.stat().st_size < MIN_FILE_SIZE:
                dest.unlink()
                stats["tiny"] += 1
                img["local_path"] = None
                continue

            h = _md5(dest)

            # Check cross-model duplicate
            if h in main_md5_index:
                main_paths = main_md5_index[h]
                own_main = str(CAMERAS_IMAGES / safe_mfr / safe_name / f"main.{ext}")
                own_main_jpg = str(CAMERAS_IMAGES / safe_mfr / safe_name / "main.jpg")
                own_main_png = str(CAMERAS_IMAGES / safe_mfr / safe_name / "main.png")
                own_mains = {own_main, own_main_jpg, own_main_png}

                if all(p not in own_mains for p in main_paths):
                    # Matches a DIFFERENT model's main.jpg — contamination
                    dest.unlink()
                    stats["cross_model_dupe"] += 1
                    img["local_path"] = None
                    continue
                else:
                    # Matches own main.jpg — same-model duplicate
                    dest.unlink()
                    stats["same_model_dupe"] += 1
                    img["local_path"] = None
                    continue

            # Passed immediate checks — track for mass-dupe pass
            extra_md5s.setdefault(h, []).append(dest)
            path_to_entry[dest] = (cam_idx, img_idx)

            if (i + 1) % 200 == 0:
                print(f"  [{i+1}/{len(extras)}] downloaded={stats['downloaded']} "
                      f"failed={stats['failed']} rejected={stats['cross_model_dupe'] + stats['same_model_dupe'] + stats['tiny']}",
                      flush=True)
                # Periodic save
                CAMERAS_JSON.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))

    # --- Mass duplicate pass ---
    print("\n  Mass duplicate check...")
    mass_dupes = {h: paths for h, paths in extra_md5s.items() if len(paths) > MASS_DUPE_THRESHOLD}
    mass_deleted = 0
    for h, paths in mass_dupes.items():
        for p in paths:
            if p.exists():
                p.unlink()
                mass_deleted += 1
            # Clear local_path in JSON
            if p in path_to_entry:
                cam_idx, img_idx = path_to_entry[p]
                cameras[cam_idx]["images"][img_idx]["local_path"] = None
    stats["mass_dupe"] = mass_deleted
    if mass_dupes:
        print(f"  Removed {mass_deleted} files across {len(mass_dupes)} duplicate hashes")

    # --- Update local_path for surviving files ---
    print("\n  Updating local_path for surviving files...")
    updated = 0
    for dest, (cam_idx, img_idx) in path_to_entry.items():
        if dest.exists():
            cameras[cam_idx]["images"][img_idx]["local_path"] = str(dest)
            updated += 1
            stats["kept"] += 1
    print(f"  Updated {updated} local_path entries")

    # --- Clean up empty directories ---
    for d in sorted(CAMERAS_IMAGES.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Recover extra camera images with validation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview what would be downloaded")
    group.add_argument("--execute", action="store_true", help="Download and validate")
    args = parser.parse_args()

    cameras = json.loads(CAMERAS_JSON.read_text())
    print(f"Loaded {len(cameras)} cameras")

    if args.dry_run:
        print("=== Recovery Plan [DRY RUN] ===")
        dry_run_report(cameras)
        print(f"\n[DRY RUN] No changes made.")
        return

    print("=== Recover Extra Images [EXECUTE] ===")
    stats = asyncio.run(download_and_validate(cameras))

    # Save updated JSON
    CAMERAS_JSON.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))

    print(f"\n=== Results ===")
    print(f"  Downloaded:          {stats['downloaded']}")
    print(f"  Failed (404/error):  {stats['failed']}")
    print(f"  Cross-model dupes:   {stats['cross_model_dupe']}")
    print(f"  Same-model dupes:    {stats['same_model_dupe']}")
    print(f"  Mass dupes:          {stats.get('mass_dupe', 0)}")
    print(f"  Tiny (<5KB):         {stats['tiny']}")
    print(f"  Kept:                {stats['kept']}")

    # Verification
    extra_files = []
    for brand_dir in CAMERAS_IMAGES.iterdir():
        if not brand_dir.is_dir() or brand_dir.name.startswith("_"):
            continue
        for model_dir in brand_dir.iterdir():
            if not model_dir.is_dir():
                continue
            for f in model_dir.iterdir():
                if f.is_file() and not f.name.startswith("main") and f.name != ".DS_Store":
                    extra_files.append(f)

    print(f"\n=== Verification ===")
    print(f"  Extra image files on disk: {len(extra_files)}")
    main_files = sum(1 for f in CAMERAS_IMAGES.rglob("main.*") if f.is_file())
    print(f"  Main image files on disk:  {main_files}")
    cameras_with_extras = sum(
        1 for c in cameras
        if any(img.get("local_path") and "main" not in img["local_path"]
               for img in c.get("images", [])[1:])
    )
    print(f"  Cameras with valid extras: {cameras_with_extras}")


if __name__ == "__main__":
    main()
