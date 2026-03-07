"""Batch camera image processing using IOPaint/LAMA for watermark removal, keeping original size."""

import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
from PIL import Image
from iopaint.model_manager import ModelManager
from iopaint.schema import InpaintRequest

TEST_DIR = Path("data/images/Test")
OUTPUT_DIR = TEST_DIR / "IOPaint_no_resize"


def create_watermark_mask(img: Image.Image) -> np.ndarray:
    """Create a mask covering the bottom strip where watermarks typically appear."""
    w, h = img.size
    strip_height = int(h * 0.15)
    strip_height = max(30, min(strip_height, 50))
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[h - strip_height :, :] = 255
    return mask


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(TEST_DIR.glob("*.jpg"))
    if not images:
        print("No test images found in", TEST_DIR)
        return

    print("Loading LAMA model...")
    model = ModelManager(name="lama", device="cpu")
    print(f"Processing {len(images)} images (no resize)...\n")

    for img_path in images:
        print(f"  {img_path.name}...", end=" ", flush=True)

        img = Image.open(img_path).convert("RGB")
        img_array = np.array(img)
        mask = create_watermark_mask(img)

        result_bgr = model(img_array, mask, InpaintRequest())
        result_rgb = result_bgr[:, :, ::-1]
        result_img = Image.fromarray(result_rgb)

        result_img.save(OUTPUT_DIR / img_path.name, quality=95)
        print(f"done ({result_img.size[0]}x{result_img.size[1]})")

    print(f"\nSaved {len(images)} images to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
