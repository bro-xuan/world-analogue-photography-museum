#!/usr/bin/env python3
"""Generate WebP thumbnails for camera tile images.

For each main.jpg in data/images/cameras/{Brand}/{Model}/,
generates a thumb.webp at 300x300 (2x retina for 150px tiles).
Also writes a colors.json mapping each camera dir to its dominant hex color.
"""

import json
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
COLORS_OUT = Path("data/images/colors.json")


def _dominant_color(img: Image.Image) -> str:
    """Return hex color string of the average color of a thumbnail."""
    small = img.copy()
    small.thumbnail((16, 16), Image.BILINEAR)
    if small.mode != "RGB":
        small = small.convert("RGB")
    pixels = list(small.getdata())
    n = len(pixels)
    r = sum(p[0] for p in pixels) // n
    g = sum(p[1] for p in pixels) // n
    b = sum(p[2] for p in pixels) // n
    return f"#{r:02x}{g:02x}{b:02x}"


def generate_thumbnail(src: Path, dst: Path) -> tuple[bool, str | None]:
    """Generate a WebP thumbnail. Returns (created, hex_color)."""
    # Skip if thumbnail is newer than source
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        # Still extract color from existing thumbnail
        try:
            with Image.open(dst) as img:
                return False, _dominant_color(img)
        except Exception:
            return False, None

    try:
        with Image.open(src) as img:
            img.thumbnail(THUMB_SIZE, Image.LANCZOS)
            # Convert to RGB if needed (handles RGBA, palette, etc.)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            color = _dominant_color(img)
            img.save(dst, "WEBP", quality=THUMB_QUALITY)
        return True, color
    except Exception as e:
        print(f"  ERROR: {src}: {e}")
        return False, None


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
    colors: dict[str, str] = {}

    for src in sources:
        dst = src.parent / THUMB_NAME
        was_created, color = generate_thumbnail(src, dst)
        if was_created:
            created += 1
        elif dst.exists():
            skipped += 1
        else:
            errors += 1

        if color:
            # Key: "Brand/Model" relative path
            rel = src.parent.relative_to(IMAGES_DIR)
            colors[str(rel)] = color

        if (created + skipped + errors) % 500 == 0:
            print(f"  Progress: {created + skipped + errors}/{len(sources)} ({created} new)")

    # Write colors mapping
    COLORS_OUT.parent.mkdir(parents=True, exist_ok=True)
    COLORS_OUT.write_text(json.dumps(colors, separators=(",", ":")))
    print(f"Wrote {COLORS_OUT} ({len(colors)} entries)")

    print(f"\nDone: {created} created, {skipped} up-to-date, {errors} errors")


if __name__ == "__main__":
    main()
