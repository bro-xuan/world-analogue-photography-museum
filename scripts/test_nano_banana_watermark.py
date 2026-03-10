"""Test Nano Banana (Gemini 2.5 Flash Image) for watermark removal on 2 chinesecamera images."""

import shutil
import sys
from io import BytesIO
from pathlib import Path

sys.path.insert(0, ".")

from google import genai
from PIL import Image

API_KEY = "AIzaSyBI_m6UlxZnTG2M6tJYITCwogM1lVUD8Sk"

PROMPT = """Remove the semi-transparent Chinese watermark text (中国相机档案 / chinesecamera.org) from this photo. The background behind the camera is plain white — fill watermark areas with clean white. Keep the camera EXACTLY as blurry, soft, and low-resolution as it appears in the original. Do NOT sharpen, enhance, add detail, or increase clarity. Do NOT invent or hallucinate any text, logos, brand names, or mechanical details. If something is unreadable in the original, leave it unreadable. Output should look identical to the input minus the watermark."""

SAMPLES = [
    ("seagull", "data/images/cameras/Seagull/Seagull_130°全景转机/main.jpg"),
    ("pearl_river", "data/images/cameras/Pearl_River/珠江_4型_Type_I/main.jpg"),
]

OUTPUT_DIR = Path("data/reports/nano_banana_test")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=API_KEY)

    for label, path in SAMPLES:
        print(f"\n--- {label}: {path} ---")

        if not Path(path).exists():
            print("  SKIP: file not found")
            continue

        # Load and downscale to 512x512
        img = Image.open(path).convert("RGB")
        img_small = img.resize((512, 512), Image.LANCZOS)
        print(f"  Input downscaled to 512x512, sending to gemini-2.5-flash-image (Nano Banana)...")

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp-image-generation",
            contents=[PROMPT, img_small],
            config=genai.types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        # Extract image from response
        saved = False
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                result_img = Image.open(BytesIO(part.inline_data.data))
                out_path = OUTPUT_DIR / f"{label}_result.png"
                result_img.save(out_path)
                print(f"  Saved: {out_path} ({out_path.stat().st_size} bytes)")
                saved = True
            elif part.text is not None:
                print(f"  Model text: {part.text[:200]}")

        if not saved:
            print("  WARNING: No image in response")

        # Copy original for comparison
        shutil.copy(path, OUTPUT_DIR / f"{label}_original.jpg")

    print(f"\nDone! Results in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
