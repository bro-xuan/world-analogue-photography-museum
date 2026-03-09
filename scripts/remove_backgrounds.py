"""Batch background removal and white canvas placement for camera images.

Removes backgrounds using rembg and places subjects on 800x800 white canvases
for a consistent museum grid appearance.

Usage:
    uv run python scripts/remove_backgrounds.py                # Process all
    uv run python scripts/remove_backgrounds.py --resume       # Skip already processed
    uv run python scripts/remove_backgrounds.py --limit 10     # First N images
    uv run python scripts/remove_backgrounds.py --dry-run      # List what would be processed
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

IMAGES_DIR = Path("data/images/cameras")
REPORTS_DIR = Path("data/reports")
RESULTS_FILE = REPORTS_DIR / "background_removal.json"
REVIEW_HTML = REPORTS_DIR / "background_removal_review.html"


def find_images(limit: int | None = None) -> list[Path]:
    """Find all main.jpg files under the cameras image directory."""
    images = sorted(IMAGES_DIR.glob("*/*/main.jpg"))
    if limit:
        images = images[:limit]
    return images


def should_skip(img_path: Path, resume: bool) -> str | None:
    """Return reason to skip, or None if image should be processed."""
    backup = img_path.parent / "main_original.jpg"
    if resume and backup.exists():
        return "already processed"
    return None


def save_results(results: list[dict]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")


def generate_review_html(results: list[dict]) -> None:
    """Generate side-by-side before/after HTML for flagged images."""
    flagged = [r for r in results if r.get("flag")]
    if not flagged:
        print("  No flagged images — no review sheet needed.")
        return

    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Background Removal Review</title>
<style>
body { font-family: -apple-system, sans-serif; background: #111; color: #eee; margin: 20px; }
h1 { color: #fff; }
h2 { color: #aaf; margin-top: 30px; border-bottom: 1px solid #333; padding-bottom: 5px; }
.summary { background: #1a1a2e; padding: 15px; border-radius: 8px; margin: 15px 0; }
.summary td { padding: 3px 15px; }
.grid { display: flex; flex-wrap: wrap; gap: 12px; }
.card { background: #222; border-radius: 4px; padding: 6px; width: 360px; text-align: center; }
.pair { display: flex; gap: 4px; justify-content: center; }
.pair img { width: 170px; height: 170px; object-fit: contain; border-radius: 2px; background: #333; }
.card .label { font-size: 11px; color: #aaa; margin-top: 4px; word-break: break-all; }
.card .flag { font-size: 10px; font-weight: bold; margin-top: 2px; color: #fa5; }
</style>
</head>
<body>
<h1>Background Removal Review</h1>
"""

    total = len(results)
    bg_removed = sum(1 for r in results if r.get("status") == "bg_removed")
    padded = sum(1 for r in results if r.get("status") == "padded_white")
    flagged_count = len(flagged)

    html += f"""<div class="summary">
<table>
<tr><td>Total images:</td><td>{total}</td></tr>
<tr><td>Background removed:</td><td>{bg_removed}</td></tr>
<tr><td>Padded to square (white bg):</td><td>{padded}</td></tr>
<tr><td style="color:#fa5">Flagged for review:</td><td>{flagged_count}</td></tr>
</table>
</div>
"""

    html += f'<h2>Flagged Images ({flagged_count})</h2>\n<div class="grid">\n'
    for r in flagged:
        original = r.get("original_path", "")
        processed_path = r.get("path", "")
        name = r.get("name", "?")
        flag = r.get("flag", "")
        alpha = r.get("alpha_coverage", 0)
        html += f"""<div class="card">
<div class="pair">
<a href="../../{original}" target="_blank"><img src="../../{original}" title="Original"></a>
<a href="../../{processed_path}" target="_blank"><img src="../../{processed_path}" title="Processed"></a>
</div>
<div class="label">{name}</div>
<div class="flag">{flag} (alpha: {alpha:.1%})</div>
</div>
"""
    html += '</div>\n</body></html>'

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_HTML.write_text(html)
    print(f"  Generated review: {REVIEW_HTML} ({flagged_count} flagged images)")


def main():
    parser = argparse.ArgumentParser(description="Remove backgrounds from camera images")
    parser.add_argument("--resume", action="store_true", help="Skip images where main_original.jpg exists")
    parser.add_argument("--limit", type=int, help="Process at most N images")
    parser.add_argument("--dry-run", action="store_true", help="List what would be processed, no changes")
    args = parser.parse_args()

    print("Scanning for images...")
    all_images = find_images()
    print(f"  Found {len(all_images)} camera images")

    # Filter to processable images
    to_process = []
    skipped_resume = 0
    for img_path in all_images:
        reason = should_skip(img_path, args.resume)
        if reason:
            skipped_resume += 1
        else:
            to_process.append(img_path)

    if args.resume and skipped_resume:
        print(f"  Already processed: {skipped_resume}, remaining: {len(to_process)}")

    if args.limit:
        to_process = to_process[: args.limit]
        print(f"  Limited to {len(to_process)} images")

    if args.dry_run:
        print(f"\n[DRY RUN] Would process {len(to_process)} images:")
        for p in to_process[:20]:
            print(f"  {p}")
        if len(to_process) > 20:
            print(f"  ... and {len(to_process) - 20} more")
        return

    if not to_process:
        print("  Nothing to process.")
        return

    # Lazy imports — rembg is heavy
    print("\nInitializing rembg session...")
    from PIL import Image
    from rembg import new_session

    from src.images.background import (
        check_alpha_coverage,
        is_already_white,
        pad_to_square,
        place_on_canvas,
        remove_background,
    )

    session = new_session("u2net")
    print("Ready.\n")

    results: list[dict] = []
    processed = 0
    padded_white = 0
    flagged = 0
    errors = 0
    t0 = time.time()

    for i, img_path in enumerate(to_process):
        brand_model = f"{img_path.parent.parent.name}/{img_path.parent.name}"

        try:
            img = Image.open(img_path).convert("RGB")

            # Backup original
            backup_path = img_path.parent / "main_original.jpg"
            if not backup_path.exists():
                img.save(backup_path, "JPEG", quality=95)

            # Check if already on white background — skip rembg, just pad to square
            if is_already_white(img):
                canvas = pad_to_square(img)
                canvas.save(img_path, "JPEG", quality=92)
                padded_white += 1
                results.append({
                    "path": str(img_path),
                    "original_path": str(backup_path),
                    "name": brand_model,
                    "status": "padded_white",
                })
                processed += 1
                continue

            # Background removal
            rgba = remove_background(img, session)
            alpha_coverage = check_alpha_coverage(rgba)

            # QA flag
            flag = None
            if alpha_coverage < 0.05:
                flag = "alpha < 5% (subject may be lost)"
                flagged += 1
            elif alpha_coverage > 0.95:
                flag = "alpha > 95% (background may not be removed)"
                flagged += 1

            # Canvas placement
            canvas = place_on_canvas(rgba)
            canvas.save(img_path, "JPEG", quality=92)

            result = {
                "path": str(img_path),
                "original_path": str(backup_path),
                "name": brand_model,
                "status": "bg_removed",
                "alpha_coverage": round(alpha_coverage, 4),
            }
            if flag:
                result["flag"] = flag
                print(f"  [{i+1}/{len(to_process)}] FLAG: {brand_model} — {flag}")
            results.append(result)
            processed += 1

        except Exception as e:
            errors += 1
            results.append({
                "path": str(img_path),
                "name": brand_model,
                "status": "error",
                "error": str(e),
            })
            print(f"  [{i+1}/{len(to_process)}] ERROR: {brand_model} — {e}")

        # Progress every 50 images
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            remaining = (len(to_process) - i - 1) / rate
            print(
                f"  [{i+1}/{len(to_process)}] {processed} processed "
                f"({padded_white} padded), {flagged} flagged "
                f"({rate:.1f}/s, ~{remaining/60:.0f}m remaining)"
            )
            save_results(results)

    # Final save
    save_results(results)

    elapsed = time.time() - t0
    print(f"\nDone: {processed} processed ({padded_white} padded, "
          f"{processed - padded_white} bg removed), {flagged} flagged, {errors} errors")
    print(f"Time: {elapsed:.0f}s ({processed/max(elapsed,1):.1f} images/s)")
    print(f"Results: {RESULTS_FILE}")

    generate_review_html(results)


if __name__ == "__main__":
    main()
