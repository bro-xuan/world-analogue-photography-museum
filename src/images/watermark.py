"""Watermark detection and removal using EasyOCR + OpenCV inpainting.

Detects watermark text in the bottom region of images via OCR pattern matching,
creates a precise mask around detected text, and inpaints using cv2.inpaint (Telea).

Extracted from scripts/process_images_precise_watermark.py for reuse.
"""

import re

import cv2
import easyocr
import numpy as np

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
PAD_H = 8
PAD_V = 5
# Safety: skip if mask exceeds this fraction of image area
MAX_MASK_FRACTION = 0.15
# OCR confidence threshold (0-1)
MIN_CONFIDENCE = 0.15
# OpenCV inpaint radius (pixels)
INPAINT_RADIUS = 5


class WatermarkDetector:
    """Detect watermark text in images using EasyOCR."""

    def __init__(self, gpu: bool = False):
        self.reader = easyocr.Reader(["en"], gpu=gpu, verbose=False)

    def detect(self, img_array: np.ndarray) -> tuple[np.ndarray | None, list[str], float]:
        """Detect watermark text and return a precise mask.

        Args:
            img_array: RGB image as numpy array (H, W, 3)

        Returns:
            Tuple of (mask, detected_texts, mask_fraction).
            mask is uint8 (H, W) with 255 for watermark areas, or None if no watermark.
            mask_fraction is the fraction of image area covered by the mask (0.0 if None).
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
            return None, [], 0.0

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
            return None, [], 0.0

        # Build mask from detected watermark bounding boxes
        mask = np.zeros((h, w), dtype=np.uint8)
        for bbox in watermark_boxes:
            pts = np.array(bbox, dtype=np.float64)
            pts /= scale
            pts[:, 1] += roi_top

            x_min = max(0, int(pts[:, 0].min()) - PAD_H)
            x_max = min(w, int(pts[:, 0].max()) + PAD_H)
            y_min = max(0, int(pts[:, 1].min()) - PAD_V)
            y_max = min(h, int(pts[:, 1].max()) + PAD_V)

            mask[y_min:y_max, x_min:x_max] = 255

        # Merge adjacent detections with dilation, then feather edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 7))
        mask = cv2.dilate(mask, kernel, iterations=1)
        mask = cv2.GaussianBlur(mask, (5, 5), 0)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

        mask_fraction = np.count_nonzero(mask) / (h * w)
        if mask_fraction > MAX_MASK_FRACTION:
            return None, detected_texts, mask_fraction

        return mask, detected_texts, mask_fraction


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


def detect_file(path: str) -> tuple[bool, list[str], float]:
    """Convenience: detect watermark in an image file.

    Args:
        path: Path to image file

    Returns:
        Tuple of (has_watermark, detected_texts, mask_fraction)
    """
    from PIL import Image

    img = Image.open(path).convert("RGB")
    img_array = np.array(img)

    detector = WatermarkDetector()
    mask, texts, fraction = detector.detect(img_array)

    return mask is not None, texts, fraction
