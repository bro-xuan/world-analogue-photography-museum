#!/usr/bin/env python3
"""Generate WebP thumbnails for camera tile images.

For each main.jpg in data/images/cameras/{Brand}/{Model}/,
generates a thumb.webp at 300x300 (2x retina for 150px tiles).
"""

import sys
from pathlib import Path

sys.path.insert(0, ".")

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required. Install with: uv add Pillow")
    sys.exit(1)

IMAGES_DIR = Path("data/images/cameras")
THUMB_SIZE = (300, 300)
THUMB_QUALITY = 75
THUMB_NAME = "thumb.webp"


def generate_thumbnail(src: Path, dst: Path) -> bool:
    """Generate a WebP thumbnail. Returns True if created/updated."""
    # Skip if thumbnail is newer than source
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return False

    try:
        with Image.open(src) as img:
            img.thumbnail(THUMB_SIZE, Image.LANCZOS)
            # Convert to RGB if needed (handles RGBA, palette, etc.)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(dst, "WEBP", quality=THUMB_QUALITY)
        return True
    except Exception as e:
        print(f"  ERROR: {src}: {e}")
        return False


def main():
    if not IMAGES_DIR.exists():
        print(f"ERROR: {IMAGES_DIR} not found")
        sys.exit(1)

    # Find all main.jpg files
    sources = sorted(IMAGES_DIR.glob("*/*/main.jpg"))
    print(f"Found {len(sources)} source images")

    created = 0
    skipped = 0
    errors = 0

    for src in sources:
        dst = src.parent / THUMB_NAME
        result = generate_thumbnail(src, dst)
        if result:
            created += 1
        elif dst.exists():
            skipped += 1
        else:
            errors += 1

        if (created + skipped + errors) % 500 == 0:
            print(f"  Progress: {created + skipped + errors}/{len(sources)} ({created} new)")

    print(f"\nDone: {created} created, {skipped} up-to-date, {errors} errors")


if __name__ == "__main__":
    main()
