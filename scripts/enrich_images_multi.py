#!/usr/bin/env python3
"""Enrich cameras with additional images from multiple new sources.

Targets cameras that have 0-1 images and tries to find more from:
1. Camera-wiki.org (MediaWiki API) — CC-licensed, multi-image per page
2. Manufacturer museums (Canon, Nikon) — official product shots
3. Google Custom Search (optional, needs GOOGLE_API_KEY + GOOGLE_CSE_ID)

Usage:
    # Enrich cameras with additional images (camera-wiki + manufacturer museums)
    uv run python scripts/enrich_images_multi.py --limit 500

    # Only target cameras with 0 images
    uv run python scripts/enrich_images_multi.py --missing-only --limit 500

    # Include Google Custom Search (requires API key)
    GOOGLE_API_KEY="..." GOOGLE_CSE_ID="..." \
    uv run python scripts/enrich_images_multi.py --limit 500

    # Download found images to disk
    uv run python scripts/enrich_images_multi.py --download --limit 500
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

import httpx

from src.images.camerawiki_search import search_camerawiki_images
from src.images.google_search import search_google_images
from src.images.manufacturer_museums import search_manufacturer_museum
from src.utils.data_io import IMAGES_DIR, MERGED_DIR
from src.utils.http import RateLimitedClient

# Flickr static CDN blocks rapid requests — use a sync client with
# browser-like headers and generous delays for downloads.
_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://camera-wiki.org/",
}


def _download_file_sync(url: str, dest: Path, retries: int = 2) -> bool:
    """Download a file with browser headers. Sync to avoid asyncio rate-limit issues."""
    import time
    for attempt in range(retries + 1):
        try:
            with httpx.Client(
                headers=_DOWNLOAD_HEADERS, timeout=30.0, follow_redirects=True
            ) as cl:
                resp = cl.get(url)
                if resp.status_code == 429:
                    wait = 30 * (attempt + 1)
                    print(f"    429 on download, waiting {wait}s...", flush=True)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    return False
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.content)
                return True
        except Exception:
            if attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            return False
    return False


def _sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    import re
    s = re.sub(r'[<>:"/\\|?*]', '_', name)
    s = re.sub(r'[\s_]+', '_', s).strip('_.')
    return s[:200] if s else 'unknown'


def _ext_from_url(url: str) -> str:
    """Extract file extension from a URL."""
    import re
    path = url.split("?")[0].split("#")[0]
    match = re.search(r"\.(\w{2,5})$", path)
    if match:
        ext = match.group(1).lower()
        if ext in ("jpg", "jpeg", "png", "gif", "webp"):
            return ext
    return "jpg"


def _count_local_images(cam: dict) -> int:
    """Count how many images have a local_path that exists on disk."""
    count = 0
    for img in cam.get("images", []):
        lp = img.get("local_path")
        if lp and Path(lp).exists():
            count += 1
    return count


async def enrich_multi_images(
    limit: int = 0,
    missing_only: bool = False,
    download: bool = False,
    max_per_camera: int = 5,
) -> None:
    """Enrich cameras with additional images from new sources."""
    cameras_path = MERGED_DIR / "cameras.json"
    if not cameras_path.exists():
        print(f"ERROR: {cameras_path} not found")
        return

    cameras = json.loads(cameras_path.read_text())
    print(f"Loaded {len(cameras)} cameras")

    # Build targets
    targets: list[tuple[int, dict]] = []
    for idx, cam in enumerate(cameras):
        n_local = _count_local_images(cam)
        if missing_only and n_local > 0:
            continue
        # Skip cameras that already have many images
        if n_local >= max_per_camera:
            continue
        targets.append((idx, cam))

    print(f"Targets: {len(targets)} cameras ({'' if missing_only else 'including those with 1 image, '}"
          f"max {max_per_camera} images each)")

    if limit > 0:
        targets = targets[:limit]
        print(f"  Limiting to first {limit}")

    stats = {
        "camerawiki": 0,
        "manufacturer": 0,
        "google": 0,
        "total_new_images": 0,
        "cameras_enriched": 0,
        "downloaded": 0,
    }

    cameras_images_dir = IMAGES_DIR / "cameras"
    project_root = Path(__file__).resolve().parent.parent

    async with RateLimitedClient(min_delay=4.0) as client:
        for i, (idx, cam) in enumerate(targets):
            name = cam.get("name", "unknown")
            mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
            existing_urls = {img.get("url", "") for img in cam.get("images", [])}
            n_existing = _count_local_images(cam)
            slots_remaining = max_per_camera - n_existing

            if slots_remaining <= 0:
                continue

            new_images: list[dict] = []

            # Skip re-searching if we already found images from these sources
            # (previous run enriched but didn't download)
            has_new_sources = any(
                img.get("source") in ("camerawiki", "canon_museum", "google")
                for img in cam.get("images", [])
                if not img.get("local_path")
            )

            if has_new_sources and download:
                # Just download the pending images, don't re-search
                pending = [
                    img for img in cam.get("images", [])
                    if img.get("source") in ("camerawiki", "canon_museum", "google")
                    and not img.get("local_path")
                ]
                if pending:
                    import time as _time

                    safe_mfr = _sanitize_filename(mfr) if mfr else "unknown"
                    safe_name = _sanitize_filename(name)
                    camera_dir = cameras_images_dir / safe_mfr / safe_name
                    existing_files = sorted(camera_dir.iterdir()) if camera_dir.is_dir() else []
                    next_idx = len(existing_files) + 1

                    for img in pending:
                        url = img.get("url", "")
                        if not url:
                            continue
                        ext = _ext_from_url(url)
                        dest = camera_dir / f"{next_idx}.{ext}"
                        if dest.exists():
                            img["local_path"] = str(dest.relative_to(project_root))
                            stats["downloaded"] += 1
                        else:
                            success = _download_file_sync(url, dest)
                            if success:
                                img["local_path"] = str(dest.relative_to(project_root))
                                stats["downloaded"] += 1
                            else:
                                stats["download_failed"] = stats.get("download_failed", 0) + 1
                            _time.sleep(1.5)
                        next_idx += 1

                    stats["cameras_enriched"] += 1
                    stats["total_new_images"] += len(pending)

                # Progress & checkpoint
                if (i + 1) % 25 == 0:
                    print(
                        f"  [{i+1}/{len(targets)}] "
                        f"downloaded={stats['downloaded']} "
                        f"failed={stats.get('download_failed', 0)} "
                        f"enriched={stats['cameras_enriched']}",
                        flush=True,
                    )
                if (i + 1) % 100 == 0:
                    cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
                    print(f"  Saved checkpoint at {i+1}", flush=True)
                continue

            # Source 1: Camera-wiki.org
            cwiki = await search_camerawiki_images(name, mfr, client, max_results=slots_remaining)
            if cwiki:
                for img in cwiki:
                    if img["url"] not in existing_urls:
                        new_images.append(img)
                        existing_urls.add(img["url"])
                        stats["camerawiki"] += 1

            # Source 2: Manufacturer museums
            if len(new_images) < slots_remaining:
                mfr_results = await search_manufacturer_museum(
                    name, mfr, client, max_results=slots_remaining - len(new_images)
                )
                if mfr_results:
                    for img in mfr_results:
                        if img["url"] not in existing_urls:
                            new_images.append(img)
                            existing_urls.add(img["url"])
                            stats["manufacturer"] += 1

            # Source 3: Google Custom Search (optional)
            if len(new_images) < slots_remaining:
                google = await search_google_images(
                    name, mfr, client, max_results=slots_remaining - len(new_images)
                )
                if google:
                    for img in google:
                        if img["url"] not in existing_urls:
                            new_images.append(img)
                            existing_urls.add(img["url"])
                            stats["google"] += 1

            if new_images:
                cam.setdefault("images", []).extend(new_images)
                stats["total_new_images"] += len(new_images)
                stats["cameras_enriched"] += 1

                # Download images if requested
                if download:
                    import time as _time

                    safe_mfr = _sanitize_filename(mfr) if mfr else "unknown"
                    safe_name = _sanitize_filename(name)
                    camera_dir = cameras_images_dir / safe_mfr / safe_name

                    # Find the next available image index
                    existing_files = sorted(camera_dir.iterdir()) if camera_dir.is_dir() else []
                    next_idx = len(existing_files) + 1

                    for img in new_images:
                        url = img.get("url", "")
                        if not url:
                            continue
                        ext = _ext_from_url(url)
                        filename = f"{next_idx}.{ext}"
                        dest = camera_dir / filename

                        if dest.exists():
                            img["local_path"] = str(dest.relative_to(project_root))
                            stats["downloaded"] += 1
                            next_idx += 1
                            continue

                        success = _download_file_sync(url, dest)
                        if success:
                            img["local_path"] = str(dest.relative_to(project_root))
                            stats["downloaded"] += 1
                        else:
                            stats.setdefault("download_failed", 0)
                            stats["download_failed"] = stats.get("download_failed", 0) + 1
                        next_idx += 1
                        _time.sleep(1.5)  # Gentle delay between Flickr downloads

            # Progress reporting
            if (i + 1) % 25 == 0:
                print(
                    f"  [{i+1}/{len(targets)}] "
                    f"camerawiki={stats['camerawiki']} "
                    f"manufacturer={stats['manufacturer']} "
                    f"google={stats['google']} "
                    f"enriched={stats['cameras_enriched']}",
                    flush=True,
                )

            # Save checkpoints
            if (i + 1) % 100 == 0:
                cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
                print(f"  Saved checkpoint at {i+1}", flush=True)

    # Final save
    cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))

    print(f"\n{'='*50}")
    print(f"Multi-image enrichment complete")
    print(f"  Cameras enriched: {stats['cameras_enriched']}")
    print(f"  New images found: {stats['total_new_images']}")
    print(f"    Camera-wiki.org: {stats['camerawiki']}")
    print(f"    Manufacturer museums: {stats['manufacturer']}")
    print(f"    Google Custom Search: {stats['google']}")
    if download:
        print(f"  Downloaded: {stats['downloaded']}")
        print(f"  Failed: {stats.get('download_failed', 0)}")
    print(f"Saved to {cameras_path}")


def main():
    args = sys.argv[1:]

    limit = 0
    missing_only = False
    do_download = False

    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        elif arg == "--missing-only":
            missing_only = True
        elif arg == "--download":
            do_download = True

    asyncio.run(enrich_multi_images(
        limit=limit,
        missing_only=missing_only,
        download=do_download,
    ))


if __name__ == "__main__":
    main()
