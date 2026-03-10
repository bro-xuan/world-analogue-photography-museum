"""Test OpenAI gpt-image-1 for watermark removal on 2 chinesecamera images."""

import base64
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")

from openai import OpenAI
from PIL import Image

API_KEY = os.environ["OPENAI_API_KEY"]

PROMPT = """Remove the semi-transparent Chinese watermark text (中国相机档案 / chinesecamera.org) from this photo. The background behind the camera is plain white — fill watermark areas with clean white. Keep the camera EXACTLY as blurry, soft, and low-resolution as it appears in the original. Do NOT sharpen, enhance, add detail, or increase clarity. Do NOT invent or hallucinate any text, logos, brand names, or mechanical details. If something is unreadable in the original, leave it unreadable. Output should look identical to the input minus the watermark."""

SAMPLES = [
    ("seagull", "data/images/cameras/Seagull/Seagull_130°全景转机/main.jpg"),
    ("pearl_river", "data/images/cameras/Pearl_River/珠江_4型_Type_I/main.jpg"),
]

OUTPUT_DIR = Path("data/reports/openai_test")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=API_KEY)

    for label, path in SAMPLES:
        print(f"\n--- {label}: {path} ---")

        if not Path(path).exists():
            print("  SKIP: file not found")
            continue

        # Downscale to 512x512 and save to temp PNG file
        img = Image.open(path).convert("RGB")
        img_small = img.resize((512, 512), Image.LANCZOS)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img_small.save(tmp, format="PNG")
            tmp_path = tmp.name

        print(f"  Input downscaled to 512x512, sending to gpt-image-1...")

        result = client.images.edit(
            model="gpt-image-1",
            image=open(tmp_path, "rb"),
            prompt=PROMPT,
            size="1024x1024",
        )

        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)

        # Save result
        image_b64 = result.data[0].b64_json
        out_path = OUTPUT_DIR / f"{label}_result_v4.png"
        out_path.write_bytes(base64.standard_b64decode(image_b64))
        print(f"  Saved: {out_path}")

        # Copy original for comparison
        shutil.copy(path, OUTPUT_DIR / f"{label}_original.jpg")

    print(f"\nDone! Results in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
