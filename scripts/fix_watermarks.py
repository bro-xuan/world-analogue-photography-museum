"""Fix watermarked camera images: auto-inpaint small ones, drop severe ones.

Based on scan results from scan_watermarks.py:
- mask_fraction < 0.05 AND image >= 20KB AND width > 200px → auto-inpaint
- mask_fraction > 0.10 OR image < 20KB → drop (clear local_path for re-download)
- Middle range (mask 5-10%) → skip (manual review via HTML contact sheet)

Usage:
    uv run python scripts/fix_watermarks.py --dry-run
    uv run python scripts/fix_watermarks.py --execute
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

from src.utils.data_io import MERGED_DIR

CAMERAS_FILE = MERGED_DIR / "cameras.json"
REPORTS_DIR = Path("data/reports")
SCAN_RESULTS = REPORTS_DIR / "watermark_scan.json"
BACKUP_DIR = Path("data/images/cameras_backup")
IMAGES_DIR = Path("data/images/cameras")


def load_cameras() -> list[dict]:
    return json.loads(CAMERAS_FILE.read_text())


def save_cameras(cameras: list[dict]) -> None:
    CAMERAS_FILE.write_text(json.dumps(cameras, indent=2, ensure_ascii=False) + "\n")


def load_scan_results() -> list[dict]:
    if not SCAN_RESULTS.exists():
        print(f"ERROR: No scan results found at {SCAN_RESULTS}")
        print("Run scan_watermarks.py first.")
        sys.exit(1)
    return json.loads(SCAN_RESULTS.read_text())


def triage(results: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Classify watermarked images into auto-inpaint, drop, and manual review.

    Returns (inpaint_list, drop_list, review_list)
    """
    inpaint_list = []
    drop_list = []
    review_list = []

    for r in results:
        if not r.get("has_watermark"):
            continue

        mf = r.get("mask_fraction", 0)
        size = r.get("file_size", 0)
        width = r.get("width", 0)

        if mf > 0.10 or size < 20_000:
            drop_list.append(r)
        elif mf < 0.05 and size >= 20_000 and width > 200:
            inpaint_list.append(r)
        else:
            review_list.append(r)

    return inpaint_list, drop_list, review_list


def backup_image(local_path: str) -> bool:
    """Copy original image to backup directory. Returns True if backed up."""
    src = Path(local_path)
    if not src.exists():
        return False

    # Preserve directory structure: cameras_backup/Brand/Model/main.jpg
    rel = src.relative_to(IMAGES_DIR)
    dst = BACKUP_DIR / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))
    return True


def inpaint_image(local_path: str, detector) -> bool:
    """Detect and inpaint watermark in image file. Returns True if inpainted."""
    import numpy as np
    from PIL import Image

    from src.images.watermark import inpaint

    try:
        img = Image.open(local_path).convert("RGB")
        img_array = np.array(img)

        mask, texts, mf = detector.detect(img_array)
        if mask is None:
            return False

        result_array = inpaint(img_array, mask)
        result_img = Image.fromarray(result_array)
        result_img.save(local_path, quality=95)
        return True
    except Exception as e:
        print(f"    ERROR inpainting {local_path}: {e}")
        return False


def clear_camera_image(cam: dict) -> None:
    """Remove image file from disk and clear local_path."""
    for img in cam.get("images", []):
        lp = img.get("local_path", "")
        if lp:
            p = Path(lp)
            if p.exists():
                p.unlink()
            del img["local_path"]
            # Clean up empty parent dir
            parent = p.parent
            try:
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            except Exception:
                pass
        break


def main():
    parser = argparse.ArgumentParser(description="Fix watermarked camera images")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview changes")
    group.add_argument("--execute", action="store_true", help="Apply fixes")
    args = parser.parse_args()

    dry_run = args.dry_run
    mode = "DRY RUN" if dry_run else "EXECUTE"
    print(f"=== Watermark Fix [{mode}] ===\n")

    # Load scan results
    scan_results = load_scan_results()
    watermarked = [r for r in scan_results if r.get("has_watermark")]
    print(f"Scan results: {len(scan_results)} total, {len(watermarked)} with watermarks")

    # Triage
    inpaint_list, drop_list, review_list = triage(scan_results)

    # ─── Step 3a: Triage summary ───
    print("\n" + "=" * 70)
    print("Step 3a: Triage")
    print("=" * 70)
    print(f"  Auto-inpaint (mask < 5%, size >= 20KB, width > 200px): {len(inpaint_list)}")
    print(f"  Drop (mask > 10% or size < 20KB):                     {len(drop_list)}")
    print(f"  Manual review (middle range):                          {len(review_list)}")

    if drop_list:
        print("\n  Images to drop:")
        for r in drop_list[:15]:
            mf = r.get("mask_fraction", 0)
            print(f"    {r['manufacturer_normalized']:15} {r['name']:35} mask:{mf:.1%} size:{r.get('file_size',0)//1024}KB")
        if len(drop_list) > 15:
            print(f"    ... and {len(drop_list) - 15} more")

    if review_list:
        print(f"\n  Images for manual review ({len(review_list)}):")
        for r in review_list[:10]:
            mf = r.get("mask_fraction", 0)
            texts = ", ".join(r.get("texts", [])[:2])
            print(f"    {r['manufacturer_normalized']:15} {r['name']:35} mask:{mf:.1%} — {texts}")
        if len(review_list) > 10:
            print(f"    ... and {len(review_list) - 10} more")

    if dry_run:
        print(f"\n[DRY RUN] No changes made. Run with --execute to apply.")
        return

    # ─── Step 3b: Backup + Inpaint ───
    print("\n" + "=" * 70)
    print("Step 3b: Inpaint qualifying images")
    print("=" * 70)

    if inpaint_list:
        print(f"  Backing up {len(inpaint_list)} images...")
        backed_up = 0
        for r in inpaint_list:
            if backup_image(r["local_path"]):
                backed_up += 1
        print(f"  Backed up {backed_up} images to {BACKUP_DIR}")

        print(f"\n  Initializing EasyOCR reader...")
        from src.images.watermark import WatermarkDetector
        detector = WatermarkDetector()

        print(f"  Inpainting {len(inpaint_list)} images...")
        inpainted = 0
        t0 = time.time()
        for i, r in enumerate(inpaint_list):
            if inpaint_image(r["local_path"], detector):
                inpainted += 1
            if (i + 1) % 25 == 0:
                elapsed = time.time() - t0
                print(f"    [{i+1}/{len(inpaint_list)}] {inpainted} inpainted ({(i+1)/elapsed:.1f}/s)")
        print(f"  Inpainted {inpainted} of {len(inpaint_list)} images")
    else:
        print("  No images qualify for auto-inpaint.")

    # ─── Step 3c: Drop severely watermarked images ───
    print("\n" + "=" * 70)
    print("Step 3c: Drop severely watermarked images")
    print("=" * 70)

    if drop_list:
        cameras = load_cameras()
        cam_by_id = {c.get("id"): c for c in cameras}
        dropped = 0
        drop_ids = set()

        for r in drop_list:
            cam_id = r["id"]
            drop_ids.add(cam_id)
            cam = cam_by_id.get(cam_id)
            if cam:
                # Backup before dropping
                backup_image(r["local_path"])
                clear_camera_image(cam)
                dropped += 1

        print(f"  Dropped {dropped} images (cleared local_path, files deleted)")

        save_cameras(cameras)
        print(f"  Saved cameras.json")

        # List dropped cameras for re-download
        dropped_report = REPORTS_DIR / "watermark_dropped.json"
        dropped_data = [{"id": r["id"], "name": r["name"], "source": r["source"]}
                        for r in drop_list]
        dropped_report.write_text(json.dumps(dropped_data, indent=2) + "\n")
        print(f"  Dropped camera list: {dropped_report}")
        print(f"  Run 'uv run python scripts/download_images.py' to find replacements")
    else:
        print("  No images to drop.")

    # ─── Summary ───
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Auto-inpainted: {len(inpaint_list)}")
    print(f"  Dropped: {len(drop_list)}")
    print(f"  Manual review (unchanged): {len(review_list)}")
    print(f"  Backups: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
