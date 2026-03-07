"""Test pipeline: watermark removal (EasyOCR) -> background removal (rembg) -> white canvas.

Combines logic from process_images_precise_watermark.py and process_images_rembg.py
into a single 3-step pipeline for evaluating image consistency on 10 test images.

Output: data/images/Test/EasyOCR/
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

import cv2
import easyocr
import numpy as np
from PIL import Image
from rembg import new_session, remove

TEST_DIR = Path("data/images/Test")
OUTPUT_DIR = TEST_DIR / "EasyOCR"

# --- Watermark detection config ---

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
    # Chinese watermark patterns
    r"中国相机",
    r"chinesecamera",
    r"档案",
]

WATERMARK_RE = re.compile("|".join(WATERMARK_PATTERNS), re.IGNORECASE)

ROI_BOTTOM_FRACTION = 0.18  # bottom 18%
ROI_TOP_FRACTION = 0.15  # top 15%
PAD_H = 8
PAD_V = 5
MAX_MASK_FRACTION = 0.15
MIN_CONFIDENCE = 0.15
INPAINT_RADIUS = 5

# --- Canvas config ---

OBJECT_SIZE = 760
CANVAS_SIZE = 800


class WatermarkDetector:
    def __init__(self):
        self.reader = easyocr.Reader(["en", "ch_sim"], gpu=False, verbose=False)

    def _scan_region(self, img_array: np.ndarray, roi_slice: np.ndarray,
                     y_offset: int) -> tuple[list, list[str]]:
        """Scan a region for watermark text, return boxes and detected texts."""
        h, w = img_array.shape[:2]
        scale = 2
        roi_up = cv2.resize(roi_slice, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_CUBIC)

        results = self.reader.readtext(roi_up)
        if not results:
            return [], []

        watermark_boxes = []
        detected_texts = []
        for bbox, text, confidence in results:
            if confidence < MIN_CONFIDENCE:
                continue
            if not WATERMARK_RE.search(text):
                continue
            # Convert bbox coords back to full-image coordinates
            pts = np.array(bbox, dtype=np.float64)
            pts /= scale
            pts[:, 1] += y_offset
            watermark_boxes.append(pts)
            detected_texts.append(f"{text} ({confidence:.0%})")

        return watermark_boxes, detected_texts

    def detect(self, img_array: np.ndarray) -> tuple[np.ndarray | None, list[str]]:
        """Detect watermark text in bottom 18% and top 15%, return mask."""
        h, w = img_array.shape[:2]
        all_boxes = []
        all_texts = []

        # Scan bottom region
        bottom_start = int(h * (1 - ROI_BOTTOM_FRACTION))
        bottom_roi = img_array[bottom_start:, :]
        boxes, texts = self._scan_region(img_array, bottom_roi, bottom_start)
        all_boxes.extend(boxes)
        all_texts.extend(texts)

        # Scan top region
        top_end = int(h * ROI_TOP_FRACTION)
        top_roi = img_array[:top_end, :]
        boxes, texts = self._scan_region(img_array, top_roi, 0)
        all_boxes.extend(boxes)
        all_texts.extend(texts)

        if not all_boxes:
            return None, []

        # Build mask
        mask = np.zeros((h, w), dtype=np.uint8)
        for pts in all_boxes:
            x_min = max(0, int(pts[:, 0].min()) - PAD_H)
            x_max = min(w, int(pts[:, 0].max()) + PAD_H)
            y_min = max(0, int(pts[:, 1].min()) - PAD_V)
            y_max = min(h, int(pts[:, 1].max()) + PAD_V)
            mask[y_min:y_max, x_min:x_max] = 255

        # Merge adjacent detections + feather
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 7))
        mask = cv2.dilate(mask, kernel, iterations=1)
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

        mask_fraction = np.count_nonzero(mask) / (h * w)
        if mask_fraction > MAX_MASK_FRACTION:
            print(f"    WARN: mask too large ({mask_fraction:.1%}), skipping inpaint")
            return None, all_texts

        return mask, all_texts


def inpaint(img_array: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Inpaint masked regions using OpenCV's Telea method."""
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    result_bgr = cv2.inpaint(img_bgr, mask, INPAINT_RADIUS, cv2.INPAINT_TELEA)
    return cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)


def remove_background(img: Image.Image, session) -> Image.Image:
    """Remove background with rembg, return RGBA image."""
    return remove(img, session=session)


def place_on_canvas(rgba_img: Image.Image) -> Image.Image:
    """Crop to subject bbox, resize to fit OBJECT_SIZE, center on white canvas."""
    # Crop to the bounding box of non-transparent pixels
    alpha = rgba_img.split()[3]
    bbox = alpha.getbbox()
    if bbox:
        rgba_img = rgba_img.crop(bbox)

    # Resize (up or down) to fit within OBJECT_SIZE, preserving aspect ratio
    w, h = rgba_img.size
    scale = min(OBJECT_SIZE / w, OBJECT_SIZE / h)
    new_w = round(w * scale)
    new_h = round(h * scale)
    rgba_img = rgba_img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255))
    x = (CANVAS_SIZE - new_w) // 2
    y = (CANVAS_SIZE - new_h) // 2
    canvas.paste(rgba_img, (x, y), rgba_img.split()[3])
    return canvas


def check_alpha_coverage(rgba_img: Image.Image) -> float:
    """Return fraction of non-transparent pixels in the RGBA image."""
    alpha = np.array(rgba_img.split()[3])
    return np.count_nonzero(alpha > 127) / alpha.size


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(TEST_DIR.glob("*.jpg"))
    if not images:
        print("No test images found in", TEST_DIR)
        return

    print("Step 0: Initializing models...")
    detector = WatermarkDetector()
    rembg_session = new_session("u2net")

    print(f"\nProcessing {len(images)} images through 3-step pipeline:\n")
    print(f"  1. Watermark removal (EasyOCR + cv2.inpaint)")
    print(f"  2. Background removal (rembg u2net)")
    print(f"  3. Canvas placement ({OBJECT_SIZE}px fit -> {CANVAS_SIZE}px canvas)\n")
    print("-" * 70)

    stats = {"total": 0, "watermarks_found": 0, "alpha_warnings": 0}

    for img_path in images:
        print(f"\n  {img_path.name}")
        stats["total"] += 1

        # Load
        img = Image.open(img_path).convert("RGB")
        img_array = np.array(img)

        # Step 1: Watermark detection + inpaint
        mask, texts = detector.detect(img_array)
        if mask is not None:
            mask_pct = np.count_nonzero(mask) / (mask.shape[0] * mask.shape[1])
            img_array = inpaint(img_array, mask)
            img = Image.fromarray(img_array)
            stats["watermarks_found"] += 1
            print(f"    [1] Watermark FOUND (mask: {mask_pct:.1%}) — {', '.join(texts)}")
        else:
            if texts:
                print(f"    [1] Watermark detected but mask skipped — {', '.join(texts)}")
            else:
                print(f"    [1] No watermark")

        # Step 2: Background removal
        rgba = remove_background(img, rembg_session)
        alpha_coverage = check_alpha_coverage(rgba)
        qa_status = "OK"
        if alpha_coverage < 0.05:
            qa_status = "WARN: alpha < 5% (subject may be lost)"
            stats["alpha_warnings"] += 1
        elif alpha_coverage > 0.95:
            qa_status = "WARN: alpha > 95% (background may not be removed)"
            stats["alpha_warnings"] += 1
        print(f"    [2] Background removed (alpha coverage: {alpha_coverage:.1%}) — {qa_status}")

        # Step 3: Canvas placement
        canvas = place_on_canvas(rgba)
        out_path = OUTPUT_DIR / img_path.name
        canvas.save(out_path, "JPEG", quality=92)
        print(f"    [3] Saved {CANVAS_SIZE}x{CANVAS_SIZE} -> {out_path.name}")

    print("\n" + "-" * 70)
    print(f"\nDone: {stats['total']} images processed")
    print(f"  Watermarks found & removed: {stats['watermarks_found']}")
    print(f"  Alpha QA warnings: {stats['alpha_warnings']}")
    print(f"  Output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
