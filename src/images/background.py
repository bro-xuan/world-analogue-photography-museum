"""Background removal and white canvas placement for camera images.

Core functions extracted from scripts/process_images_test_pipeline.py.
"""

import numpy as np
from PIL import Image

OBJECT_SIZE = 760
CANVAS_SIZE = 800


def remove_background(img: Image.Image, session) -> Image.Image:
    """Remove background with rembg, return RGBA image."""
    from rembg import remove

    return remove(img, session=session)


def place_on_canvas(
    rgba_img: Image.Image, object_size: int = OBJECT_SIZE, canvas_size: int = CANVAS_SIZE
) -> Image.Image:
    """Crop to subject bbox, resize to fit object_size, center on white canvas."""
    alpha = rgba_img.split()[3]
    bbox = alpha.getbbox()
    if bbox:
        rgba_img = rgba_img.crop(bbox)

    w, h = rgba_img.size
    scale = min(object_size / w, object_size / h)
    new_w = round(w * scale)
    new_h = round(h * scale)
    rgba_img = rgba_img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (canvas_size, canvas_size), (255, 255, 255))
    x = (canvas_size - new_w) // 2
    y = (canvas_size - new_h) // 2
    canvas.paste(rgba_img, (x, y), rgba_img.split()[3])
    return canvas


def check_alpha_coverage(rgba_img: Image.Image) -> float:
    """Return fraction of non-transparent pixels in the RGBA image."""
    alpha = np.array(rgba_img.split()[3])
    return np.count_nonzero(alpha > 127) / alpha.size


def pad_to_square(img: Image.Image, canvas_size: int = CANVAS_SIZE) -> Image.Image:
    """Resize RGB image to fit canvas_size and center on white square canvas."""
    w, h = img.size
    if w == h == canvas_size:
        return img
    scale = min(canvas_size / w, canvas_size / h)
    new_w = round(w * scale)
    new_h = round(h * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (canvas_size, canvas_size), (255, 255, 255))
    x = (canvas_size - new_w) // 2
    y = (canvas_size - new_h) // 2
    canvas.paste(resized, (x, y))
    return canvas


def is_already_white(img: Image.Image, threshold: int = 245) -> bool:
    """Check if image already has a white background by sampling 4 corner regions.

    Returns True if >= 3 of 4 corners are predominantly white.
    """
    arr = np.array(img.convert("RGB"))
    h, w = arr.shape[:2]
    # Sample 5% corner regions
    size_h = max(1, h // 20)
    size_w = max(1, w // 20)

    corners = [
        arr[:size_h, :size_w],          # top-left
        arr[:size_h, -size_w:],         # top-right
        arr[-size_h:, :size_w],         # bottom-left
        arr[-size_h:, -size_w:],        # bottom-right
    ]

    white_count = 0
    for corner in corners:
        mean_rgb = corner.mean(axis=(0, 1))
        if all(c >= threshold for c in mean_rgb):
            white_count += 1

    return white_count >= 3
