"""Precise watermark removal using EasyOCR text detection + OpenCV inpainting.

Instead of masking the entire bottom strip (which distorts camera parts),
this detects only the watermark text via OCR, creates a tight mask around it,
and inpaints just that small area using cv2.inpaint (Telea method).

Since precise masks are very small (1-3% of image), OpenCV inpainting
produces excellent results — no need for LAMA's heavy model.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

import cv2
import easyocr
import numpy as np
from PIL import Image

TEST_DIR = Path("data/images/Test")
OUTPUT_DIR = TEST_DIR / "IOPaint_precise"

# Watermark patterns — text that indicates a watermark, NOT camera branding
WATERMARK_PATTERNS = [
    r"\(c\)",
    r"©",
    r"flickr",
    r"collectiblend",
    r"courtesy",
    r"ebay",
    r"\.com",
    r"\.org",
    r"\.net",
    r"//",
    r"photo by",
    r"image by",
    r"credit",
    r"photographer",
    r"fotograf",
    r"westlich",
    r"blog\d+",
    r"fc2",
    r"all rights",
    r"reserved",
]

WATERMARK_RE = re.compile("|".join(WATERMARK_PATTERNS), re.IGNORECASE)

# Bottom region to scan (fraction of image height)
ROI_FRACTION = 0.18
# Padding around detected text (pixels)
PAD_H = 8  # horizontal
PAD_V = 5  # vertical
# Safety: skip if mask exceeds this fraction of image area
MAX_MASK_FRACTION = 0.15
# OCR confidence threshold (0-1)
MIN_CONFIDENCE = 0.15
# OpenCV inpaint radius (pixels) — how far to look for replacement pixels
INPAINT_RADIUS = 5


class WatermarkDetector:
    def __init__(self):
        self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    def detect(self, img_array: np.ndarray) -> tuple[np.ndarray | None, list[str]]:
        """Detect watermark text and return a precise mask.

        Args:
            img_array: RGB image as numpy array (H, W, 3)

        Returns:
            Tuple of (mask, detected_texts). Mask is uint8 (H, W) with 255 for
            watermark areas, or None if no watermark found.
        """
        h, w = img_array.shape[:2]
        roi_top = int(h * (1 - ROI_FRACTION))
        roi = img_array[roi_top:, :]

        # Upscale 2x for better OCR on small watermark text
        scale = 2
        roi_up = cv2.resize(roi, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_CUBIC)

        results = self.reader.readtext(roi_up)
        if not results:
            return None, []

        watermark_boxes = []
        detected_texts = []
        for bbox, text, confidence in results:
            if confidence < MIN_CONFIDENCE:
                continue
            if not WATERMARK_RE.search(text):
                continue
            watermark_boxes.append(bbox)
            detected_texts.append(f"{text} ({confidence:.0%})")

        if not watermark_boxes:
            return None, []

        # Build mask from detected watermark bounding boxes
        mask = np.zeros((h, w), dtype=np.uint8)
        for bbox in watermark_boxes:
            # bbox is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] — four corners in upscaled ROI
            pts = np.array(bbox, dtype=np.float64)
            # Scale back to original resolution
            pts /= scale
            # Offset from ROI coordinates to full image coordinates
            pts[:, 1] += roi_top

            # Get bounding rect with padding
            x_min = max(0, int(pts[:, 0].min()) - PAD_H)
            x_max = min(w, int(pts[:, 0].max()) + PAD_H)
            y_min = max(0, int(pts[:, 1].min()) - PAD_V)
            y_max = min(h, int(pts[:, 1].max()) + PAD_V)

            mask[y_min:y_max, x_min:x_max] = 255

        # Merge adjacent detections with dilation, then feather edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 7))
        mask = cv2.dilate(mask, kernel, iterations=1)
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        # Re-threshold after blur to keep binary
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

        # Safety check: mask shouldn't be too large
        mask_fraction = np.count_nonzero(mask) / (h * w)
        if mask_fraction > MAX_MASK_FRACTION:
            print(f"WARN: mask too large ({mask_fraction:.1%}), skipping")
            return None, detected_texts

        return mask, detected_texts


def inpaint(img_array: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Inpaint masked regions using OpenCV's Telea method.

    Args:
        img_array: RGB image as numpy array (H, W, 3)
        mask: Binary mask, uint8 (H, W), 255 = inpaint region

    Returns:
        Inpainted RGB image as numpy array.
    """
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    result_bgr = cv2.inpaint(img_bgr, mask, INPAINT_RADIUS, cv2.INPAINT_TELEA)
    return cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(TEST_DIR.glob("*.jpg"))
    if not images:
        print("No test images found in", TEST_DIR)
        return

    print("Initializing EasyOCR reader...")
    detector = WatermarkDetector()

    print(f"Processing {len(images)} images...\n")

    stats = {"processed": 0, "skipped": 0, "inpainted": 0}

    for img_path in images:
        print(f"  {img_path.name}...", end=" ", flush=True)

        img = Image.open(img_path).convert("RGB")
        img_array = np.array(img)

        mask, texts = detector.detect(img_array)

        if mask is None:
            img.save(OUTPUT_DIR / img_path.name, quality=95)
            print("no watermark, copied original")
            stats["skipped"] += 1
        else:
            mask_pct = np.count_nonzero(mask) / (mask.shape[0] * mask.shape[1])
            result_array = inpaint(img_array, mask)
            result_img = Image.fromarray(result_array)
            result_img.save(OUTPUT_DIR / img_path.name, quality=95)
            print(f"inpainted (mask: {mask_pct:.1%}) — detected: {', '.join(texts)}")
            stats["inpainted"] += 1

            # Also save the mask for debugging
            mask_dir = OUTPUT_DIR / "masks"
            mask_dir.mkdir(exist_ok=True)
            cv2.imwrite(str(mask_dir / img_path.name), mask)

        stats["processed"] += 1

    print(f"\nDone: {stats['processed']} processed, "
          f"{stats['inpainted']} inpainted, "
          f"{stats['skipped']} skipped (no watermark)")
    print(f"Results saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
