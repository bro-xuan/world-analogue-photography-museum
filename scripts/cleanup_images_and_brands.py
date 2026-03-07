"""Clean up camera images and fix brand normalization.

Handles:
1. Delete all flickr_search images (confirmed wrong — landscapes/portraits, not cameras)
2. Fix brand normalization in cameras.json
3. Merge brand image directories
4. Rebuild all local_path entries from disk
5. Clean up empty directories

Usage:
    uv run python scripts/cleanup_images_and_brands.py --dry-run
    uv run python scripts/cleanup_images_and_brands.py --execute
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.utils.data_io import MERGED_DIR

CAMERAS_IMAGES = Path("data/images/cameras")
CAMERAS_JSON = MERGED_DIR / "cameras.json"

# Format folders to delete (all contents are flickr_search junk)
FORMAT_FOLDERS = {"135", "120", "4x5"}

# Brand normalization fixes: old_value -> new_value
BRAND_FIXES = {
    "Zeiss Ikon": "Zeiss",
    "Canon Camera": "Canon",
    "Canonet": "Canon",
    "Asahi Optical Co": "Pentax",
    "Asahi Optical Co.,": "Pentax",
    "Great": "Great Wall",
    "Great Wall Plastic Factory, Lomographische": "Diana",
    "Halina/Ansco": "Halina",
    "Shen Hao": "Shenhao",
}

# Directory merges: source_dir_name -> target_dir_name
DIR_MERGES = {
    "Zeiss_Ikon": "Zeiss",
    "Canon_Camera": "Canon",
    "Canonet": "Canon",
    "Asahi_Optical_Co": "Pentax",
    "Halina_Ansco": "Halina",
    "Great_Wall_Plastic_Factory,_Lomographische": "Diana",
    "Shen_Hao": "Shenhao",
}


def _sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    s = re.sub(r'[<>:"/\\|?*]', "_", name)
    s = re.sub(r"[\s_]+", "_", s).strip("_.")
    return s[:200] if s else "unknown"


def load_cameras() -> list[dict]:
    return json.loads(CAMERAS_JSON.read_text())


def save_cameras(cameras: list[dict]) -> None:
    CAMERAS_JSON.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"  Saved {len(cameras)} cameras to {CAMERAS_JSON}")


# --- Step 1: Delete flickr_search images ---

def find_format_folder_files() -> list[Path]:
    """Find all files inside format subfolders (135/, 120/, 4x5/)."""
    files = []
    for brand_dir in sorted(CAMERAS_IMAGES.iterdir()):
        if not brand_dir.is_dir():
            continue
        for sub in brand_dir.iterdir():
            if sub.is_dir() and sub.name in FORMAT_FOLDERS:
                for f in sub.rglob("*"):
                    if f.is_file() and f.name != ".DS_Store":
                        files.append(f)
    return files


def step1_delete_flickr_search(cameras: list[dict], dry_run: bool) -> list[dict]:
    """Delete all flickr_search images from disk and cameras.json."""
    print("\n=== Step 1: Delete flickr_search images ===")

    # Find format folder files on disk
    format_files = find_format_folder_files()
    print(f"  Files in format folders: {len(format_files)}")

    # Count flickr_search entries in JSON
    fs_count = 0
    for cam in cameras:
        for img in cam.get("images", []):
            if img.get("source") == "flickr_search":
                fs_count += 1
    print(f"  flickr_search entries in JSON: {fs_count}")

    if dry_run:
        if format_files:
            print(f"  Would delete {len(format_files)} files in format folders")
            for f in format_files[:10]:
                print(f"    {f}")
            if len(format_files) > 10:
                print(f"    ... and {len(format_files) - 10} more")
        print(f"  Would remove {fs_count} flickr_search image entries from cameras.json")
        return cameras

    # Delete files
    for f in format_files:
        f.unlink()
    print(f"  Deleted {len(format_files)} files")

    # Remove flickr_search entries from cameras.json
    removed = 0
    for cam in cameras:
        original = cam.get("images", [])
        filtered = [img for img in original if img.get("source") != "flickr_search"]
        if len(filtered) < len(original):
            removed += len(original) - len(filtered)
            cam["images"] = filtered
    print(f"  Removed {removed} flickr_search image entries")

    return cameras


# --- Step 2: Fix brand normalization ---

def step2_fix_brands(cameras: list[dict], dry_run: bool) -> list[dict]:
    """Update manufacturer_normalized for known mismatches."""
    print("\n=== Step 2: Fix brand normalization ===")

    changes = []
    for cam in cameras:
        old_val = cam.get("manufacturer_normalized", "")
        if old_val in BRAND_FIXES:
            new_val = BRAND_FIXES[old_val]
            changes.append((cam["name"], old_val, new_val))
            if not dry_run:
                cam["manufacturer_normalized"] = new_val
                # Update country too
                from src.normalization.manufacturers import MANUFACTURER_COUNTRIES
                country = MANUFACTURER_COUNTRIES.get(new_val)
                if country:
                    cam["manufacturer_country"] = country

    print(f"  Brand fixes to apply: {len(changes)}")
    for name, old, new in changes[:15]:
        print(f"    {name}: {old} -> {new}")
    if len(changes) > 15:
        print(f"    ... and {len(changes) - 15} more")

    return cameras


# --- Step 3: (manufacturers.py is edited separately) ---


# --- Step 4: Merge brand image directories ---

def step4_merge_dirs(dry_run: bool) -> None:
    """Move model subdirectories from old brand dirs into target brand dirs."""
    print("\n=== Step 4: Merge brand image directories ===")

    for src_name, tgt_name in DIR_MERGES.items():
        src_dir = CAMERAS_IMAGES / src_name
        if not src_dir.exists():
            continue

        tgt_dir = CAMERAS_IMAGES / tgt_name
        # List model subdirs (skip format folders which were cleaned in step 1)
        model_dirs = [d for d in src_dir.iterdir() if d.is_dir() and d.name not in FORMAT_FOLDERS]

        if not model_dirs:
            if not dry_run:
                # Remove empty source dir
                shutil.rmtree(src_dir, ignore_errors=True)
            print(f"  {src_name}/ -> {tgt_name}/ (empty, removing source)")
            continue

        # Check for collisions
        if tgt_dir.exists():
            existing = {d.name for d in tgt_dir.iterdir() if d.is_dir()}
            collisions = [d.name for d in model_dirs if d.name in existing]
            if collisions:
                print(f"  WARNING: {src_name} -> {tgt_name}: {len(collisions)} collisions: {collisions[:5]}")

        print(f"  {src_name}/ -> {tgt_name}/ ({len(model_dirs)} model dirs)")

        if dry_run:
            for d in model_dirs[:5]:
                print(f"    {d.name}/")
            if len(model_dirs) > 5:
                print(f"    ... and {len(model_dirs) - 5} more")
            continue

        tgt_dir.mkdir(parents=True, exist_ok=True)
        for model_dir in model_dirs:
            dest = tgt_dir / model_dir.name
            if dest.exists():
                # Merge contents into existing dir
                for item in model_dir.iterdir():
                    shutil.move(str(item), str(dest / item.name))
                model_dir.rmdir()
            else:
                shutil.move(str(model_dir), str(dest))

        # Remove source dir (may still have empty format folders)
        shutil.rmtree(src_dir, ignore_errors=True)
        print(f"    Removed {src_name}/")


# --- Step 5: Rebuild all local_path entries ---

def step5_rebuild_paths(cameras: list[dict], dry_run: bool) -> list[dict]:
    """Rebuild local_path for every camera based on what's on disk."""
    print("\n=== Step 5: Rebuild local_path entries ===")

    # Build set of all files on disk for fast lookup
    disk_files = set()
    for f in CAMERAS_IMAGES.rglob("*"):
        if f.is_file() and f.name != ".DS_Store":
            disk_files.add(str(f))

    found = 0
    cleared = 0
    unchanged = 0
    total_images = 0

    for cam in cameras:
        mfr = cam.get("manufacturer_normalized", cam.get("manufacturer", "Unknown"))
        name = cam["name"]
        brand_dir = _sanitize_filename(mfr)
        model_dir = _sanitize_filename(name)

        expected_jpg = f"data/images/cameras/{brand_dir}/{model_dir}/main.jpg"
        expected_png = f"data/images/cameras/{brand_dir}/{model_dir}/main.png"

        if expected_jpg in disk_files:
            new_path = expected_jpg
        elif expected_png in disk_files:
            new_path = expected_png
        else:
            new_path = None

        for img in cam.get("images", []):
            total_images += 1
            old_path = img.get("local_path")

            if new_path:
                if old_path == new_path:
                    unchanged += 1
                else:
                    found += 1
                    if not dry_run:
                        img["local_path"] = new_path
            else:
                if old_path is not None:
                    cleared += 1
                    if not dry_run:
                        img["local_path"] = None
                else:
                    unchanged += 1

    cameras_with_images = sum(
        1 for cam in cameras
        if any(
            (img.get("local_path") if dry_run else img.get("local_path")) is not None
            for img in cam.get("images", [])
        )
    )

    # For dry-run, compute what the count would be after changes
    if dry_run:
        would_have = 0
        for cam in cameras:
            mfr = cam.get("manufacturer_normalized", cam.get("manufacturer", "Unknown"))
            # Apply brand fix for accurate path prediction
            mfr_fixed = BRAND_FIXES.get(mfr, mfr)
            name = cam["name"]
            brand_dir = _sanitize_filename(mfr_fixed)
            model_dir = _sanitize_filename(name)
            expected_jpg = f"data/images/cameras/{brand_dir}/{model_dir}/main.jpg"
            expected_png = f"data/images/cameras/{brand_dir}/{model_dir}/main.png"
            if expected_jpg in disk_files or expected_png in disk_files:
                would_have += 1
        print(f"  Cameras that would have valid images: {would_have}")

    print(f"  Total image entries: {total_images}")
    print(f"  Paths set/updated: {found}")
    print(f"  Paths cleared (no file on disk): {cleared}")
    print(f"  Paths unchanged: {unchanged}")

    return cameras


# --- Step 6: Clean up empty directories ---

def step6_cleanup(dry_run: bool) -> None:
    """Remove empty directories and .DS_Store files."""
    print("\n=== Step 6: Clean up empty directories ===")

    # Remove .DS_Store files
    ds_files = list(CAMERAS_IMAGES.rglob(".DS_Store"))
    if ds_files:
        print(f"  .DS_Store files: {len(ds_files)}")
        if not dry_run:
            for f in ds_files:
                f.unlink()

    # Remove empty directories (bottom-up)
    removed = 0
    for d in sorted(CAMERAS_IMAGES.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            if dry_run:
                print(f"    Would remove empty: {d}")
            else:
                d.rmdir()
            removed += 1

    # Also check _orphans
    orphans_dir = CAMERAS_IMAGES / "_orphans"
    if orphans_dir.exists() and not any(orphans_dir.iterdir()):
        if not dry_run:
            orphans_dir.rmdir()
        removed += 1

    print(f"  Empty directories to remove: {removed}")


def main():
    parser = argparse.ArgumentParser(description="Clean up camera images and fix brand normalization")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes")
    group.add_argument("--execute", action="store_true", help="Execute changes")
    args = parser.parse_args()

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "EXECUTE"
    print(f"=== Camera Image & Brand Cleanup [{mode}] ===")

    cameras = load_cameras()
    print(f"Loaded {len(cameras)} cameras")

    # Step 1: Delete flickr_search images
    cameras = step1_delete_flickr_search(cameras, dry_run)

    # Step 2: Fix brand normalization
    cameras = step2_fix_brands(cameras, dry_run)

    # Step 4: Merge brand image directories
    step4_merge_dirs(dry_run)

    # Step 5: Rebuild local_path entries
    cameras = step5_rebuild_paths(cameras, dry_run)

    # Step 6: Clean up empty dirs
    step6_cleanup(dry_run)

    if not dry_run:
        save_cameras(cameras)

        # Final verification
        print("\n=== Verification ===")
        cameras = load_cameras()
        total_lp = sum(1 for c in cameras for img in c.get("images", []) if img.get("local_path"))
        broken_lp = sum(
            1 for c in cameras for img in c.get("images", [])
            if img.get("local_path") and not Path(img["local_path"]).exists()
        )
        cameras_with_imgs = sum(
            1 for c in cameras
            if any(img.get("local_path") for img in c.get("images", []))
        )
        cameras_without = len(cameras) - cameras_with_imgs

        print(f"  Cameras with images: {cameras_with_imgs}")
        print(f"  Cameras without images: {cameras_without}")
        print(f"  Total local_path entries: {total_lp}")
        print(f"  Broken local_path entries: {broken_lp}")

        # Count files on disk
        disk_count = sum(1 for f in CAMERAS_IMAGES.rglob("*") if f.is_file() and f.name != ".DS_Store")
        print(f"  Files on disk: {disk_count}")

        # Check no flickr_search remains
        fs_remaining = sum(1 for c in cameras for img in c.get("images", []) if img.get("source") == "flickr_search")
        print(f"  flickr_search entries remaining: {fs_remaining}")

        # Check no old brand dirs remain
        for old_dir in DIR_MERGES:
            p = CAMERAS_IMAGES / old_dir
            if p.exists():
                print(f"  WARNING: Old brand dir still exists: {p}")
    else:
        print(f"\n[DRY RUN] No changes made.")


if __name__ == "__main__":
    main()
