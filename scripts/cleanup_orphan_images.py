"""Delete orphan numbered images and _orphans directory.

The image download pipeline saved multiple images per camera (2.jpg, 3.jpg, etc.)
but only main.jpg is referenced in cameras.json. Many numbered files contain wrong
images — photos of completely different camera models from the same brand's search/scrape
results. The _orphans/ directory contains unreferenced files from prior reorganization.

Usage:
    uv run python scripts/cleanup_orphan_images.py --dry-run
    uv run python scripts/cleanup_orphan_images.py --execute
"""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, ".")

CAMERAS_IMAGES = Path("data/images/cameras")


def find_orphan_numbered_files() -> list[Path]:
    """Find all files in camera model dirs that are NOT main.jpg or main.png."""
    orphans = []
    for brand_dir in sorted(CAMERAS_IMAGES.iterdir()):
        if not brand_dir.is_dir() or brand_dir.name.startswith("_"):
            continue
        for model_dir in sorted(brand_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            for f in sorted(model_dir.iterdir()):
                if f.is_file() and f.name not in ("main.jpg", "main.png", ".DS_Store"):
                    orphans.append(f)
    return orphans


def step1_delete_numbered_orphans(dry_run: bool) -> int:
    """Delete all non-main files from camera model directories."""
    print("\n=== Step 1: Delete numbered orphan files ===")

    orphans = find_orphan_numbered_files()
    print(f"  Orphan files found: {len(orphans)}")

    if not orphans:
        return 0

    # Show sample
    for f in orphans[:10]:
        print(f"    {f.relative_to(CAMERAS_IMAGES)}")
    if len(orphans) > 10:
        print(f"    ... and {len(orphans) - 10} more")

    if not dry_run:
        for f in orphans:
            f.unlink()
        print(f"  Deleted {len(orphans)} files")

    return len(orphans)


def step2_delete_orphans_dir(dry_run: bool) -> int:
    """Delete the _orphans/ directory entirely."""
    print("\n=== Step 2: Delete _orphans/ directory ===")

    orphans_dir = CAMERAS_IMAGES / "_orphans"
    if not orphans_dir.exists():
        print("  _orphans/ directory does not exist, skipping")
        return 0

    file_count = sum(1 for f in orphans_dir.rglob("*") if f.is_file() and f.name != ".DS_Store")
    print(f"  Files in _orphans/: {file_count}")

    if not dry_run:
        shutil.rmtree(orphans_dir)
        print(f"  Deleted _orphans/ directory ({file_count} files)")

    return file_count


def step3_cleanup_empty_dirs(dry_run: bool) -> int:
    """Remove empty directories left after deletion."""
    print("\n=== Step 3: Clean up empty directories ===")

    # Remove .DS_Store files first
    ds_files = list(CAMERAS_IMAGES.rglob(".DS_Store"))
    if ds_files and not dry_run:
        for f in ds_files:
            f.unlink()

    # Remove empty directories bottom-up
    removed = 0
    for d in sorted(CAMERAS_IMAGES.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            if dry_run:
                print(f"    Would remove empty: {d.relative_to(CAMERAS_IMAGES)}")
            else:
                d.rmdir()
            removed += 1

    print(f"  Empty directories to remove: {removed}")
    return removed


def main():
    parser = argparse.ArgumentParser(description="Delete orphan numbered images and _orphans directory")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes without deleting")
    group.add_argument("--execute", action="store_true", help="Execute deletions")
    args = parser.parse_args()

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "EXECUTE"
    print(f"=== Orphan Image Cleanup [{mode}] ===")

    total_deleted = 0
    total_deleted += step1_delete_numbered_orphans(dry_run)
    total_deleted += step2_delete_orphans_dir(dry_run)
    empty_dirs = step3_cleanup_empty_dirs(dry_run)

    print(f"\n=== Summary ===")
    if dry_run:
        print(f"  Would delete {total_deleted} orphan files")
        print(f"  Would remove {empty_dirs} empty directories")
        print(f"\n[DRY RUN] No changes made.")
    else:
        print(f"  Deleted {total_deleted} files")
        print(f"  Removed {empty_dirs} empty directories")

        # Verification
        remaining_numbered = find_orphan_numbered_files()
        orphans_dir = CAMERAS_IMAGES / "_orphans"
        main_files = sum(1 for f in CAMERAS_IMAGES.rglob("main.*") if f.is_file())
        print(f"\n=== Verification ===")
        print(f"  Remaining non-main files: {len(remaining_numbered)}")
        print(f"  _orphans/ exists: {orphans_dir.exists()}")
        print(f"  main.jpg/png files on disk: {main_files}")


if __name__ == "__main__":
    main()
