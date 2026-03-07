"""Remove backgrounds from camera images using rembg and place on white 800x800 canvas."""

import sys
from pathlib import Path

sys.path.insert(0, ".")

from PIL import Image
from rembg import new_session, remove

INPUT_DIR = Path("data/images/Test")
OUTPUT_DIR = INPUT_DIR / "rembg"
CANVAS_SIZE = 800


def process_image(path: Path, session) -> Path:
    img = Image.open(path).convert("RGB")
    # Remove background -> RGBA with transparency
    result = remove(img, session=session)
    # Create white canvas
    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255))
    # Resize to fit within canvas, preserving aspect ratio
    result.thumbnail((CANVAS_SIZE, CANVAS_SIZE), Image.LANCZOS)
    # Center on canvas, using alpha channel as mask
    x = (CANVAS_SIZE - result.width) // 2
    y = (CANVAS_SIZE - result.height) // 2
    canvas.paste(result, (x, y), result.split()[3])
    # Save as JPG
    out_path = OUTPUT_DIR / path.name
    canvas.save(out_path, "JPEG", quality=92)
    return out_path


def main():
    images = sorted(INPUT_DIR.glob("*.jpg"))
    if not images:
        print(f"No JPG files found in {INPUT_DIR}")
        return

    print(f"Found {len(images)} images in {INPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = new_session("u2net")
    for i, path in enumerate(images, 1):
        print(f"[{i}/{len(images)}] Processing {path.name}...")
        out = process_image(path, session)
        print(f"  -> {out}")

    print(f"\nDone! Output in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
