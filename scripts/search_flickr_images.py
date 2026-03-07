"""Search Flickr for images of cameras that are missing them.

Uses Scrapling (headless browser) to scrape Flickr search results.
No API key needed. Downloads into per-camera folders.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.images.flickr_search import search_flickr_images
from src.utils.data_io import IMAGES_DIR, MERGED_DIR

CAMERAS_IMAGES_DIR = IMAGES_DIR / "cameras"


def _sanitize_filename(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', '_', name)
    s = re.sub(r'[\s_]+', '_', s).strip('_.')
    return s[:200] if s else 'unknown'


def _ext_from_url(url: str) -> str:
    path = url.split("?")[0].split("#")[0]
    match = re.search(r"\.(\w{2,5})$", path)
    if match:
        ext = match.group(1).lower()
        if ext in ("jpg", "jpeg", "png", "gif", "webp"):
            return ext
    return "jpg"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Search Flickr for missing camera images")
    parser.add_argument("--max-images", type=int, default=3, help="Max images per camera")
    parser.add_argument("--limit", type=int, default=0, help="Max cameras to search (0=all)")
    parser.add_argument("--download", action="store_true", help="Also download found images")
    args = parser.parse_args()

    cameras_path = MERGED_DIR / "cameras.json"
    cameras = json.loads(cameras_path.read_text())
    project_root = Path(__file__).resolve().parent.parent

    # Find cameras without images
    missing = []
    for i, camera in enumerate(cameras):
        has_local = any(img.get("local_path") for img in camera.get("images", []))
        if not has_local:
            missing.append((i, camera))

    print(f"Cameras missing images: {len(missing)}", flush=True)
    if args.limit:
        missing = missing[:args.limit]
        print(f"Limiting to first {args.limit}", flush=True)

    found_count = 0
    downloaded_count = 0
    import httpx

    client = httpx.Client(timeout=30.0, follow_redirects=True, verify=False) if args.download else None

    try:
        for search_idx, (cam_idx, camera) in enumerate(missing):
            mfr = camera.get("manufacturer_normalized", "")
            name = camera.get("name", "unknown")

            results = search_flickr_images(name, mfr, max_results=args.max_images)

            if results:
                found_count += 1
                camera.setdefault("images", []).extend(results)

                if args.download:
                    safe_mfr = _sanitize_filename(mfr) if mfr else "unknown"
                    safe_camera = _sanitize_filename(name)
                    camera_dir = CAMERAS_IMAGES_DIR / safe_mfr / safe_camera
                    camera_dir.mkdir(parents=True, exist_ok=True)

                    for img_idx, img in enumerate(results):
                        url = img.get("url", "")
                        if not url:
                            continue
                        ext = _ext_from_url(url)
                        filename = "main." + ext if img_idx == 0 else f"{img_idx + 1}.{ext}"
                        dest = camera_dir / filename
                        if dest.exists():
                            img["local_path"] = str(dest.relative_to(project_root))
                            downloaded_count += 1
                            continue
                        try:
                            resp = client.get(url)
                            if resp.status_code < 400:
                                dest.write_bytes(resp.content)
                                img["local_path"] = str(dest.relative_to(project_root))
                                downloaded_count += 1
                        except Exception as e:
                            print(f"  Download failed: {e}", flush=True)

                print(f"  [{search_idx+1}/{len(missing)}] FOUND {len(results)} for {mfr} {name}", flush=True)
            else:
                if (search_idx + 1) % 20 == 0:
                    print(f"  [{search_idx+1}/{len(missing)}] searched, found={found_count}, "
                          f"downloaded={downloaded_count}", flush=True)

            # Periodic save every 50 cameras
            if (search_idx + 1) % 50 == 0:
                cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    finally:
        if client:
            client.close()
        # Final save
        cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))

    print(f"\nDone. Searched: {len(missing)}, Found: {found_count}, "
          f"Downloaded: {downloaded_count}", flush=True)


if __name__ == "__main__":
    main()
