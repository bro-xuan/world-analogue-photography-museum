"""Batch camera image processing using Stable Diffusion Inpainting for watermark removal + resize."""

import sys
import os
from pathlib import Path

sys.path.insert(0, ".")

import numpy as np
import torch
from PIL import Image
from diffusers import StableDiffusionInpaintPipeline

TEST_DIR = Path("data/images/Test")
OUTPUT_DIR = TEST_DIR / "Stable diffusion"
TARGET_SIZE = 800
SD_SIZE = 512


def create_watermark_mask(img: Image.Image) -> Image.Image:
    """Create a mask covering the bottom strip where watermarks typically appear."""
    w, h = img.size
    strip_height = int(h * 0.15)
    strip_height = max(30, min(strip_height, 50))
    mask = Image.new("L", (w, h), 0)
    mask.paste(255, (0, h - strip_height, w, h))
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

    # Select device
    if torch.backends.mps.is_available():
        device = "mps"
        dtype = torch.float32  # MPS requires float32
    elif torch.cuda.is_available():
        device = "cuda"
        dtype = torch.float16
    else:
        device = "cpu"
        dtype = torch.float32

    print(f"Loading SD inpainting model on {device}...")
    pipe = StableDiffusionInpaintPipeline.from_pretrained(
        "stable-diffusion-v1-5/stable-diffusion-inpainting",
        torch_dtype=dtype,
    )
    pipe = pipe.to(device)
    pipe.set_progress_bar_config(disable=True)
    print(f"Processing {len(images)} images...\n")

    for img_path in images:
        print(f"  {img_path.name}...", end=" ", flush=True)

        img = Image.open(img_path).convert("RGB")
        mask = create_watermark_mask(img)

        # Resize to SD native resolution for inpainting
        img_sd = img.resize((SD_SIZE, SD_SIZE), Image.LANCZOS)
        mask_sd = mask.resize((SD_SIZE, SD_SIZE), Image.NEAREST)

        result = pipe(
            prompt="camera product photo, clean surface",
            negative_prompt="text, watermark, logo",
            image=img_sd,
            mask_image=mask_sd,
            num_inference_steps=30,
            guidance_scale=7.5,
        ).images[0]

        # Resize back to original aspect ratio then to target
        result = result.resize(img.size, Image.LANCZOS)
        result = resize_with_padding(result)
        result.save(OUTPUT_DIR / img_path.name, quality=95)
        print("done")

    print(f"\nSaved {len(images)} images to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
