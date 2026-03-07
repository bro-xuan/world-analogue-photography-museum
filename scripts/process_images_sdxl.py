"""Hybrid LAMA + SDXL pipeline: watermark removal, intelligent background outpainting.

Pipeline:
  1. LAMA watermark removal (bottom strip mask)
  2. Expand canvas to 800x800, center camera, fill with detected bg color
  3. SDXL inpainting ONLY on expanded border regions
  4. Composite original camera back over center (safety guarantee)

Key principle: SDXL never touches the camera pixels.
"""

import argparse
import gc
import math
import sys
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import torch
from PIL import Image, ImageFilter

TEST_DIR = Path("data/images/Test")
OUTPUT_DIR = TEST_DIR / "SDXL"
TARGET_SIZE = 800
TARGET_AREA_RATIO = 0.40  # Camera occupies ~40% of canvas area
MAX_DIM = 700  # Never exceed 87.5% of canvas on any axis
MIN_DIM = 300  # Never shrink below this


def create_watermark_mask(img: Image.Image) -> np.ndarray:
    """Create a mask covering the bottom 15% strip where watermarks appear."""
    w, h = img.size
    strip_height = int(h * 0.15)
    strip_height = max(30, min(strip_height, 50))
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[h - strip_height :, :] = 255
    return mask


def detect_bg_color(img: Image.Image) -> tuple[int, int, int]:
    """Detect dominant background color from edge pixels (median of 5px border strips)."""
    arr = np.array(img)
    h, w = arr.shape[:2]
    border = 5
    pixels = np.concatenate([
        arr[:border, :, :].reshape(-1, 3),      # top
        arr[-border:, :, :].reshape(-1, 3),      # bottom
        arr[:, :border, :].reshape(-1, 3),       # left
        arr[:, -border:, :].reshape(-1, 3),      # right
    ])
    median = np.median(pixels, axis=0).astype(int)
    return tuple(median)


def classify_background(color: tuple[int, int, int]) -> str:
    """Classify background brightness for SDXL prompt selection."""
    brightness = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
    if brightness > 200:
        return "white"
    elif brightness > 100:
        return "gray"
    else:
        return "dark"


def get_sdxl_prompt(bg_class: str) -> tuple[str, str]:
    """Return (prompt, negative_prompt) based on background classification."""
    prompts = {
        "white": (
            "clean white studio background, product photography, soft even lighting",
            "text, watermark, logo, camera, object, shadow, pattern",
        ),
        "gray": (
            "clean neutral gray studio background, product photography, even lighting",
            "text, watermark, logo, camera, object, shadow, pattern",
        ),
        "dark": (
            "clean dark studio background, product photography, dramatic lighting",
            "text, watermark, logo, camera, object, bright spots, pattern",
        ),
    }
    return prompts.get(bg_class, prompts["white"])


def compute_area_scale(w: int, h: int, target_size: int = TARGET_SIZE) -> float:
    """Compute scale factor so camera area is ~40% of canvas area.

    Clamps so no dimension exceeds MAX_DIM or falls below MIN_DIM.
    """
    canvas_area = target_size * target_size
    target_area = canvas_area * TARGET_AREA_RATIO
    scale = math.sqrt(target_area / (w * h))

    new_w = int(w * scale)
    new_h = int(h * scale)

    # Clamp: max dimension <= MAX_DIM
    max_current = max(new_w, new_h)
    if max_current > MAX_DIM:
        scale *= MAX_DIM / max_current

    # Clamp: min dimension >= MIN_DIM
    new_w = int(w * scale)
    new_h = int(h * scale)
    min_current = min(new_w, new_h)
    if min_current < MIN_DIM:
        scale *= MIN_DIM / min_current

    return scale


def expand_canvas(
    img: Image.Image, target: int = TARGET_SIZE
) -> tuple[Image.Image, Image.Image, tuple[int, int], Image.Image]:
    """Scale camera using area-based sizing and center on expanded canvas.

    Returns:
        canvas: 800x800 image with camera centered on bg-colored fill
        mask: PIL "L" image, white=border (to inpaint), black=camera (to keep)
        offset: (x, y) paste position of the scaled camera
        scaled_camera: the scaled camera image for compositing
    """
    bg_color = detect_bg_color(img)
    w, h = img.size

    # Area-based scaling for consistent visual weight
    scale = compute_area_scale(w, h, target)
    new_w = int(w * scale)
    new_h = int(h * scale)

    scaled_camera = img.resize((new_w, new_h), Image.LANCZOS)

    # Create canvas filled with detected bg color
    canvas = Image.new("RGB", (target, target), bg_color)
    offset_x = (target - new_w) // 2
    offset_y = (target - new_h) // 2
    canvas.paste(scaled_camera, (offset_x, offset_y))

    # Create mask: white = new border areas, black = original camera
    mask = Image.new("L", (target, target), 255)
    camera_mask = Image.new("L", (new_w, new_h), 0)
    mask.paste(camera_mask, (offset_x, offset_y))

    area_pct = (new_w * new_h) / (target * target) * 100
    print(f"({w}x{h} -> {new_w}x{new_h}, {area_pct:.0f}% area)", end=" ", flush=True)

    return canvas, mask, (offset_x, offset_y), scaled_camera


def step1_lama_watermark_removal(images: list[Path]) -> dict[Path, Image.Image]:
    """Remove watermarks from all images using LAMA, return cleaned images."""
    from iopaint.model_manager import ModelManager
    from iopaint.schema import InpaintRequest

    print("Loading LAMA model...")
    model = ModelManager(name="lama", device="cpu")

    results = {}
    for img_path in images:
        print(f"  [LAMA] {img_path.name}...", end=" ", flush=True)
        img = Image.open(img_path).convert("RGB")
        img_array = np.array(img)
        mask = create_watermark_mask(img)

        result_bgr = model(img_array, mask, InpaintRequest())
        result_rgb = result_bgr[:, :, ::-1]
        results[img_path] = Image.fromarray(result_rgb)
        print("done")

    # Free LAMA memory
    del model
    gc.collect()
    print("LAMA model unloaded.\n")

    return results


def step2_3_4_sdxl_outpaint_and_composite(
    cleaned_images: dict[Path, Image.Image],
) -> dict[Path, Image.Image]:
    """Expand canvas, SDXL inpaint borders, composite camera back."""
    print("Loading SDXL inpainting model...")
    from diffusers import StableDiffusionXLInpaintPipeline

    # Device selection
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"

    pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
        "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
        torch_dtype=torch.float16,
        variant="fp16",
    )

    # Memory optimizations for M3 24GB
    pipe.enable_attention_slicing("max")
    pipe.enable_vae_tiling()
    if device == "mps":
        pipe = pipe.to(device)
    else:
        pipe.enable_sequential_cpu_offload()
    pipe.set_progress_bar_config(disable=True)

    print(f"SDXL loaded on {device}.\n")

    results = {}
    for img_path, cleaned_img in cleaned_images.items():
        print(f"  [SDXL] {img_path.name} ", end="", flush=True)

        # Step 2: Expand canvas
        canvas, mask, offset, scaled_camera = expand_canvas(cleaned_img)
        bg_color = detect_bg_color(cleaned_img)
        bg_class = classify_background(bg_color)
        prompt, negative_prompt = get_sdxl_prompt(bg_class)

        # Blur mask edges for smooth blending (feathered edge)
        mask_blurred = mask.filter(ImageFilter.GaussianBlur(radius=8))

        # Step 3: SDXL inpainting on border regions only
        result = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=canvas,
            mask_image=mask_blurred,
            num_inference_steps=25,
            guidance_scale=7.5,
            height=TARGET_SIZE,
            width=TARGET_SIZE,
        ).images[0]

        # Step 4: Composite - paste original camera back (safety guarantee)
        # Create a feathered paste mask for smooth edges
        paste_mask = Image.new("L", (scaled_camera.width, scaled_camera.height), 255)
        paste_mask = paste_mask.filter(ImageFilter.GaussianBlur(radius=2))
        result.paste(scaled_camera, offset, paste_mask)

        results[img_path] = result
        print("done")

    del pipe
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    elif torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("\nSDXL model unloaded.")

    return results


def step2_4_solid_fill_and_composite(
    cleaned_images: dict[Path, Image.Image],
) -> dict[Path, Image.Image]:
    """Fast mode: expand canvas with solid bg color fill, no SDXL."""
    results = {}
    for img_path, cleaned_img in cleaned_images.items():
        print(f"  [Fill] {img_path.name} ", end="", flush=True)
        canvas, _, offset, scaled_camera = expand_canvas(cleaned_img)
        # Composite camera back (same safety guarantee)
        paste_mask = Image.new("L", (scaled_camera.width, scaled_camera.height), 255)
        paste_mask = paste_mask.filter(ImageFilter.GaussianBlur(radius=2))
        canvas.paste(scaled_camera, offset, paste_mask)
        results[img_path] = canvas
        print("done")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Hybrid LAMA + SDXL camera image processing"
    )
    parser.add_argument(
        "--no-sdxl",
        action="store_true",
        help="Skip SDXL outpainting, use solid color background fill instead",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(TEST_DIR.glob("*.jpg"))
    if not images:
        print("No test images found in", TEST_DIR)
        return

    print(f"Found {len(images)} images in {TEST_DIR}")
    mode = "solid fill" if args.no_sdxl else "SDXL outpainting"
    print(f"Mode: LAMA watermark removal + {mode}\n")

    # Step 1: LAMA watermark removal
    cleaned_images = step1_lama_watermark_removal(images)

    # Steps 2-4: Canvas expansion + outpainting + compositing
    if args.no_sdxl:
        final_images = step2_4_solid_fill_and_composite(cleaned_images)
    else:
        final_images = step2_3_4_sdxl_outpaint_and_composite(cleaned_images)

    # Save results
    print(f"\nSaving {len(final_images)} images to {OUTPUT_DIR}...")
    for img_path, result in final_images.items():
        result.save(OUTPUT_DIR / img_path.name, quality=95)

    print(f"Done! {len(final_images)} images saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
