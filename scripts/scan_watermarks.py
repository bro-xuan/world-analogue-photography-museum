"""Batch watermark scanner for camera images.

Scans main.jpg files for watermark text using EasyOCR and outputs structured
results + an HTML review contact sheet.

Usage:
    uv run python scripts/scan_watermarks.py                          # Scan all
    uv run python scripts/scan_watermarks.py --source collectiblend   # One source
    uv run python scripts/scan_watermarks.py --resume                 # Continue interrupted
    uv run python scripts/scan_watermarks.py --limit 100              # First N images
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from src.utils.data_io import MERGED_DIR

CAMERAS_FILE = MERGED_DIR / "cameras.json"
REPORTS_DIR = Path("data/reports")
SCAN_RESULTS = REPORTS_DIR / "watermark_scan.json"
REVIEW_HTML = REPORTS_DIR / "watermark_review.html"


def load_cameras() -> list[dict]:
    return json.loads(CAMERAS_FILE.read_text())


def get_scannable_images(cameras: list[dict], source_filter: str | None = None) -> list[dict]:
    """Get list of cameras with images to scan.

    Returns list of dicts with: id, name, manufacturer_normalized, source, local_path
    """
    entries = []
    for cam in cameras:
        imgs = cam.get("images", [])
        if not imgs:
            continue
        img = imgs[0]
        lp = img.get("local_path", "")
        if not lp or not Path(lp).exists():
            continue
        src = img.get("source", "unknown")
        if source_filter and src != source_filter:
            continue
        entries.append({
            "id": cam.get("id", ""),
            "name": cam.get("name", "?"),
            "manufacturer_normalized": cam.get("manufacturer_normalized", "?"),
            "source": src,
            "local_path": lp,
        })
    return entries


def load_existing_results() -> dict[str, dict]:
    """Load existing scan results for resume support."""
    if SCAN_RESULTS.exists():
        data = json.loads(SCAN_RESULTS.read_text())
        return {r["id"]: r for r in data}
    return {}


def save_results(results: dict[str, dict]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCAN_RESULTS.write_text(
        json.dumps(list(results.values()), indent=2, ensure_ascii=False) + "\n"
    )


def generate_review_html(results: dict[str, dict]) -> None:
    """Generate HTML contact sheet of flagged images sorted by severity."""
    flagged = [r for r in results.values() if r.get("has_watermark")]
    flagged.sort(key=lambda r: r.get("mask_fraction", 0), reverse=True)

    if not flagged:
        print("  No watermarks detected — no review sheet needed.")
        return

    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Watermark Review</title>
<style>
body { font-family: -apple-system, sans-serif; background: #111; color: #eee; margin: 20px; }
h1 { color: #fff; }
h2 { color: #aaf; margin-top: 30px; border-bottom: 1px solid #333; padding-bottom: 5px; }
.grid { display: flex; flex-wrap: wrap; gap: 8px; }
.card { background: #222; border-radius: 4px; padding: 4px; width: 220px; text-align: center; }
.card img { width: 220px; height: 160px; object-fit: cover; border-radius: 2px; cursor: pointer; }
.card img:hover { outline: 2px solid #ff0; }
.card .label { font-size: 11px; color: #aaa; margin-top: 4px; word-break: break-all; max-height: 40px; overflow: hidden; }
.card .severity { font-size: 10px; font-weight: bold; margin-top: 2px; }
.card .severity.high { color: #f55; }
.card .severity.medium { color: #fa5; }
.card .severity.low { color: #5f5; }
.card .texts { font-size: 9px; color: #888; margin-top: 2px; max-height: 24px; overflow: hidden; }
.stats { color: #888; font-size: 14px; }
.summary { background: #1a1a2e; padding: 15px; border-radius: 8px; margin: 15px 0; }
.summary td { padding: 3px 15px; }
</style>
</head>
<body>
<h1>Watermark Review</h1>
"""

    # Summary stats
    total = len(results)
    flagged_count = len(flagged)
    high = sum(1 for r in flagged if r.get("mask_fraction", 0) > 0.10)
    medium = sum(1 for r in flagged if 0.03 <= r.get("mask_fraction", 0) <= 0.10)
    low = sum(1 for r in flagged if r.get("mask_fraction", 0) < 0.03)

    html += f"""<div class="summary">
<table>
<tr><td>Total scanned:</td><td>{total}</td></tr>
<tr><td>Watermarks detected:</td><td>{flagged_count} ({flagged_count*100/max(total,1):.1f}%)</td></tr>
<tr><td style="color:#f55">High severity (&gt;10%):</td><td>{high} (drop)</td></tr>
<tr><td style="color:#fa5">Medium severity (3-10%):</td><td>{medium} (manual review)</td></tr>
<tr><td style="color:#5f5">Low severity (&lt;3%):</td><td>{low} (auto-inpaint)</td></tr>
</table>
</div>
"""

    # Group by severity
    severity_groups = [
        ("High Severity (drop candidates)", [r for r in flagged if r.get("mask_fraction", 0) > 0.10], "high"),
        ("Medium Severity (manual review)", [r for r in flagged if 0.03 <= r.get("mask_fraction", 0) <= 0.10], "medium"),
        ("Low Severity (auto-inpaint)", [r for r in flagged if r.get("mask_fraction", 0) < 0.03], "low"),
    ]

    for title, items, severity_class in severity_groups:
        if not items:
            continue
        html += f'<h2>{title} ({len(items)} images)</h2>\n<div class="grid">\n'
        for r in items:
            lp = r.get("local_path", "")
            name = r.get("name", "?")
            mf = r.get("mask_fraction", 0)
            texts = ", ".join(r.get("texts", [])[:3])
            src = r.get("source", "?")
            html += f"""<div class="card">
<a href="../../{lp}" target="_blank"><img src="../../{lp}" loading="lazy"></a>
<div class="label">{name}</div>
<div class="severity {severity_class}">mask: {mf:.1%} | {src}</div>
<div class="texts">{texts}</div>
</div>
"""
        html += '</div>\n'

    html += "</body></html>"
    REVIEW_HTML.write_text(html)
    print(f"  Generated review: {REVIEW_HTML} ({len(flagged)} flagged images)")


def main():
    parser = argparse.ArgumentParser(description="Scan camera images for watermarks")
    parser.add_argument("--source", type=str, help="Only scan images from this source (e.g., collectiblend)")
    parser.add_argument("--resume", action="store_true", help="Continue from previous scan")
    parser.add_argument("--limit", type=int, help="Scan at most N images")
    args = parser.parse_args()

    print("Loading cameras...")
    cameras = load_cameras()
    entries = get_scannable_images(cameras, args.source)
    print(f"  Found {len(entries)} images to scan" + (f" (source: {args.source})" if args.source else ""))

    # Resume support
    results = load_existing_results() if args.resume else {}
    if args.resume and results:
        already_done = sum(1 for e in entries if e["id"] in results)
        print(f"  Already scanned: {already_done}, remaining: {len(entries) - already_done}")
        entries = [e for e in entries if e["id"] not in results]

    if args.limit:
        entries = entries[:args.limit]
        print(f"  Limited to {len(entries)} images")

    if not entries:
        print("  Nothing to scan.")
        generate_review_html(results)
        return

    # Lazy import — these are heavy
    print("\nInitializing EasyOCR reader (first run downloads model)...")
    import numpy as np
    from PIL import Image

    from src.images.watermark import WatermarkDetector

    detector = WatermarkDetector()
    print("Ready.\n")

    scanned = 0
    detected = 0
    errors = 0
    t0 = time.time()

    for i, entry in enumerate(entries):
        path = entry["local_path"]
        name = entry["name"]

        try:
            img = Image.open(path).convert("RGB")
            img_array = np.array(img)
            w, h = img.size

            mask, texts, mask_fraction = detector.detect(img_array)

            result = {
                "id": entry["id"],
                "name": name,
                "manufacturer_normalized": entry["manufacturer_normalized"],
                "source": entry["source"],
                "local_path": path,
                "has_watermark": mask is not None,
                "texts": texts,
                "mask_fraction": mask_fraction,
                "width": w,
                "height": h,
                "file_size": Path(path).stat().st_size,
            }
            results[entry["id"]] = result

            if mask is not None:
                detected += 1
                print(f"  [{i+1}/{len(entries)}] WATERMARK: {name} — {', '.join(texts[:2])} ({mask_fraction:.1%})")
            else:
                if (i + 1) % 100 == 0:
                    elapsed = time.time() - t0
                    rate = (i + 1) / elapsed
                    remaining = (len(entries) - i - 1) / rate
                    print(f"  [{i+1}/{len(entries)}] {detected} watermarks found so far ({rate:.1f}/s, ~{remaining/60:.0f}m remaining)")

            scanned += 1

        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{len(entries)}] ERROR: {name} — {e}")

        # Save progress every 50 images
        if (scanned + 1) % 50 == 0:
            save_results(results)

    # Final save
    save_results(results)

    elapsed = time.time() - t0
    print(f"\nDone: {scanned} scanned, {detected} watermarks detected, {errors} errors")
    print(f"Time: {elapsed:.0f}s ({scanned/max(elapsed,1):.1f} images/s)")
    print(f"Results: {SCAN_RESULTS}")

    # Generate review HTML
    generate_review_html(results)


if __name__ == "__main__":
    main()
