"""Test Flux 1.1 Pro on Replicate for watermark removal on 2 chinesecamera images."""

import base64
import io
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from PIL import Image

REPLICATE_API_TOKEN = os.environ["REPLICATE_API_TOKEN"]

PROMPT = """This is a blurry, low-quality scan of a vintage analogue camera from the 1980s. ONLY remove the semi-transparent Chinese watermark text overlay (中国相机档案 / chinesecamera.org). Do NOT enhance, sharpen, upscale, or restore the image in any way. The result must look EXACTLY as blurry, soft, and low-fidelity as the original — like a bad photocopy from 1985. Do NOT add detail, clarity, or sharpness that is not in the original. Do NOT invent or recreate any text, brand names, engravings, serial numbers, or mechanical details — if something is unreadable or blurry in the original, it must stay equally unreadable and blurry. Just remove the watermark and fill in what was behind it with the same soft, blurry quality as the surrounding area. White background. Keep it ugly and old-looking."""

SAMPLES = [
    ("seagull", "data/images/cameras/Seagull/Seagull_130°全景转机/main.jpg"),
    ("pearl_river", "data/images/cameras/Pearl_River/珠江_4型_Type_I/main.jpg"),
]

OUTPUT_DIR = Path("data/reports/flux_test")


def image_to_data_uri(path: str, size: int = 512) -> str:
    img = Image.open(path).convert("RGB")
    img_small = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img_small.save(buf, format="PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def replicate_api(input_data: dict) -> str:
    """Call Replicate API via curl to avoid SSL issues, return output URL."""
    # Create prediction
    payload = json.dumps({"input": input_data})
    result = subprocess.run(
        [
            "curl", "-s", "-X", "POST",
            "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions",
            "-H", f"Authorization: Bearer {REPLICATE_API_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", payload,
        ],
        capture_output=True, text=True,
    )
    resp = json.loads(result.stdout)
    if resp.get("status") == 429:
        wait = resp.get("retry_after", 10)
        print(f"  Rate limited, waiting {wait}s...")
        time.sleep(wait + 2)
        # Retry
        result = subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                "https://api.replicate.com/v1/models/black-forest-labs/flux-1.1-pro/predictions",
                "-H", f"Authorization: Bearer {REPLICATE_API_TOKEN}",
                "-H", "Content-Type: application/json",
                "-d", payload,
            ],
            capture_output=True, text=True,
        )
        resp = json.loads(result.stdout)
    if "error" in resp and resp["error"]:
        raise RuntimeError(f"API error: {resp['error']}")
    if "id" not in resp:
        raise RuntimeError(f"Unexpected response: {json.dumps(resp)[:500]}")

    pred_id = resp["id"]
    poll_url = resp["urls"]["get"]
    print(f"  Prediction {pred_id} created, polling...")

    # Poll until complete
    for _ in range(120):
        time.sleep(2)
        result = subprocess.run(
            [
                "curl", "-s",
                poll_url,
                "-H", f"Authorization: Bearer {REPLICATE_API_TOKEN}",
            ],
            capture_output=True, text=True,
        )
        resp = json.loads(result.stdout)
        status = resp["status"]
        if status == "succeeded":
            return resp["output"]
        elif status == "failed":
            raise RuntimeError(f"Prediction failed: {resp.get('error')}")
        elif status == "canceled":
            raise RuntimeError("Prediction canceled")
        print(f"  Status: {status}...")

    raise RuntimeError("Timeout waiting for prediction")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for label, path in SAMPLES:
        print(f"\n--- {label}: {path} ---")

        if not Path(path).exists():
            print("  SKIP: file not found")
            continue

        data_uri = image_to_data_uri(path, size=512)
        print(f"  Input downscaled to 512x512, sending to flux-1.1-pro...")

        output_url = replicate_api({
            "prompt": PROMPT,
            "image": data_uri,
            "prompt_upsampling": False,
            "width": 512,
            "height": 512,
            "safety_tolerance": 5,
        })

        print(f"  Downloading result...")
        result = subprocess.run(
            ["curl", "-s", "-L", "-o", str(OUTPUT_DIR / f"{label}_flux.png"), output_url],
            capture_output=True, text=True,
        )

        out_path = OUTPUT_DIR / f"{label}_flux.png"
        print(f"  Saved: {out_path} ({out_path.stat().st_size} bytes)")

        shutil.copy(path, OUTPUT_DIR / f"{label}_original.jpg")

    print(f"\nDone! Results in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
