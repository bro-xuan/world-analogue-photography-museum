"""Test LaMa inpainting on 3 chinesecamera images with center watermarks.

All chinesecamera.org images have the same semi-transparent watermark:
"中国相机档案" (Chinese Camera Archives) + "chinesecamera.org"
overlaid in the center of the image.

This script tests LaMa inpainting quality on 3 samples from different brands.
Uses OCR with contrast enhancement to detect the watermark, with a fixed-position
fallback since the watermark location is consistent across all images.
"""

import sys
from pathlib import Path

sys.path.insert(0, ".")

import cv2
import easyocr
import numpy as np
from PIL import Image, ImageEnhance
from simple_lama_inpainting import SimpleLama

# 3 sample images from different brands (Seagull, Pearl River, Phenix)
SAMPLES = [
    ("seagull", "data/images/cameras/Seagull/Seagull_130°全景转机/main.jpg"),
    ("pearl_river", "data/images/cameras/Pearl_River/珠江_4型_Type_I/main.jpg"),
    ("phenix", "data/images/cameras/Phenix/Phenix_1999型/main.jpg"),
]

# Watermark text patterns for chinesecamera.org
WATERMARK_KEYWORDS = [
    "中国",
    "相机",
    "档案",
    "chinesecamera",
    ".org",
    "camera.org",
]

OUTPUT_DIR = Path("data/reports/lama_test")

# Mask padding and dilation settings
PAD_PX = 20
DILATE_KERNEL_SIZE = 30
DILATE_ITERATIONS = 2


def enhance_for_ocr(img_array: np.ndarray) -> np.ndarray:
    """Enhance image contrast to make semi-transparent watermark more visible."""
    # Convert to LAB and boost contrast on L channel
    lab = cv2.cvtColor(img_array, cv2.COLOR_RGB2LAB)
    l_channel = lab[:, :, 0]

    # Apply CLAHE (adaptive histogram equalization) for local contrast
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_channel)
    lab[:, :, 0] = l_enhanced
    enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    # Further sharpen
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    enhanced = cv2.filter2D(enhanced, -1, kernel)

    return enhanced


def try_ocr_detection(
    img_array: np.ndarray, reader: easyocr.Reader
) -> tuple[np.ndarray | None, list[str]]:
    """Try to detect watermark via OCR on the center region with enhancement."""
    h, w = img_array.shape[:2]

    # Focus on center region where watermark lives (30-70% height, 10-90% width)
    y1, y2 = int(h * 0.30), int(h * 0.70)
    x1, x2 = int(w * 0.10), int(w * 0.90)
    center_crop = img_array[y1:y2, x1:x2]

    # Enhance contrast to make semi-transparent text visible
    enhanced = enhance_for_ocr(center_crop)

    # Upscale 2x for better OCR
    enhanced_up = cv2.resize(enhanced, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    results = reader.readtext(enhanced_up)
    if not results:
        return None, []

    watermark_boxes = []
    detected_texts = []
    all_texts = []

    for bbox, text, confidence in results:
        all_texts.append(f"{text} ({confidence:.0%})")
        if confidence < 0.05:
            continue
        text_lower = text.lower().replace(" ", "")
        if any(kw in text_lower for kw in WATERMARK_KEYWORDS):
            watermark_boxes.append((bbox, y1, x1))  # store crop offset
            detected_texts.append(f"{text} ({confidence:.0%})")

    if not watermark_boxes:
        return None, all_texts

    # Build mask in full image coordinates
    mask = np.zeros((h, w), dtype=np.uint8)
    for bbox, crop_y, crop_x in watermark_boxes:
        pts = np.array(bbox, dtype=np.float64)
        # Scale back from 2x upscale and add crop offset
        pts /= 2.0
        pts[:, 0] += crop_x
        pts[:, 1] += crop_y

        x_min = max(0, int(pts[:, 0].min()) - PAD_PX)
        x_max = min(w, int(pts[:, 0].max()) + PAD_PX)
        y_min = max(0, int(pts[:, 1].min()) - PAD_PX)
        y_max = min(h, int(pts[:, 1].max()) + PAD_PX)
        mask[y_min:y_max, x_min:x_max] = 255

    # Dilate to merge adjacent boxes
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (DILATE_KERNEL_SIZE, DILATE_KERNEL_SIZE)
    )
    mask = cv2.dilate(mask, kernel, iterations=DILATE_ITERATIONS)

    return mask, detected_texts


def fixed_position_mask(h: int, w: int) -> np.ndarray:
    """Create a fixed mask covering the known watermark region.

    The chinesecamera.org watermark is always 2 lines in the center:
    - Line 1: "中国相机档案" (~45-53% height)
    - Line 2: "chinesecamera.org" (~53-60% height)
    - Horizontal: roughly centered, ~20-80% width
    """
    mask = np.zeros((h, w), dtype=np.uint8)

    # Watermark region (generous to cover all variations)
    y1 = int(h * 0.42)
    y2 = int(h * 0.62)
    x1 = int(w * 0.12)
    x2 = int(w * 0.88)
    mask[y1:y2, x1:x2] = 255

    return mask


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Initializing EasyOCR (ch_sim + en)...")
    reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)

    print("Initializing SimpleLama...")
    lama = SimpleLama()

    for i, (label, path) in enumerate(SAMPLES, 1):
        print(f"\n--- Sample {i}: {label} ({path}) ---")

        if not Path(path).exists():
            print("  SKIP: file not found")
            continue

        img = Image.open(path).convert("RGB")
        img_array = np.array(img)
        h, w = img_array.shape[:2]
        print(f"  Image size: {w}x{h}")

        # Try OCR detection first
        mask, texts = try_ocr_detection(img_array, reader)
        if mask is not None:
            mask_frac = np.count_nonzero(mask) / (h * w)
            print(f"  OCR detected watermark: {texts}")
            print(f"  OCR mask coverage: {mask_frac:.1%}")
            method = "ocr"
        else:
            print(f"  OCR texts (no watermark match): {texts[:5]}")
            print("  Falling back to fixed-position mask")
            mask = fixed_position_mask(h, w)
            mask_frac = np.count_nonzero(mask) / (h * w)
            print(f"  Fixed mask coverage: {mask_frac:.1%}")
            method = "fixed"

        # Save original
        img.save(OUTPUT_DIR / f"sample{i}_original.jpg", quality=95)

        # Save mask
        Image.fromarray(mask).save(OUTPUT_DIR / f"sample{i}_mask.png")

        # Run LaMa inpainting
        mask_pil = Image.fromarray(mask)
        result = lama(img, mask_pil)
        result.save(OUTPUT_DIR / f"sample{i}_result.jpg", quality=95)

        print(
            f"  Saved: sample{i}_original.jpg, sample{i}_mask.png, "
            f"sample{i}_result.jpg (method: {method})"
        )

    print(f"\nDone! Results in {OUTPUT_DIR}/")
    print(f"  open {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
