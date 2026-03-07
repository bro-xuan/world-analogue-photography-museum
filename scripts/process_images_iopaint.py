"""Batch camera image processing using IOPaint/LAMA for watermark removal + resize."""

import sys
import os
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
from PIL import Image
from iopaint.model_manager import ModelManager
from iopaint.schema import InpaintRequest

TEST_DIR = Path("data/images/Test")
OUTPUT_DIR = TEST_DIR / "IOPaint"
TARGET_SIZE = 800


def create_watermark_mask(img: Image.Image) -> np.ndarray:
    """Create a mask covering the bottom strip where watermarks typically appear."""
    w, h = img.size
    strip_height = int(h * 0.15)
    strip_height = max(30, min(strip_height, 50))
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[h - strip_height :, :] = 255
    return mask


def resize_with_padding(img: Image.Image, target: int = TARGET_SIZE) -> Image.Image:
    """Resize maintaining aspect ratio, pad with white to target x target."""
    img.thumbnail((target, target), Image.LANCZOS)
    result = Image.new("RGB", (target, target), (255, 255, 255))
    offset_x = (target - img.width) // 2
    offset_y = (target - img.height) // 2
    result.paste(img, (offset_x, offset_y))
    return result


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(TEST_DIR.glob("*.jpg"))
    if not images:
        print("No test images found in", TEST_DIR)
        return

    print(f"Loading LAMA model...")
    model = ModelManager(name="lama", device="cpu")
    print(f"Processing {len(images)} images...\n")

    for img_path in images:
        print(f"  {img_path.name}...", end=" ", flush=True)

        img = Image.open(img_path).convert("RGB")
        img_array = np.array(img)
        mask = create_watermark_mask(img)

        result_bgr = model(img_array, mask, InpaintRequest())
        # IOPaint returns BGR numpy array, convert to RGB
        result_rgb = result_bgr[:, :, ::-1]
        result_img = Image.fromarray(result_rgb)

        result_img = resize_with_padding(result_img)
        result_img.save(OUTPUT_DIR / img_path.name, quality=95)
        print("done")

    print(f"\nSaved {len(images)} images to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
