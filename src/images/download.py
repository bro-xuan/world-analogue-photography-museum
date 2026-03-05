"""Download images for cameras and films from all sources.

For cameras without images, searches Wikimedia Commons by camera name.
"""

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import unquote

from src.utils.data_io import IMAGES_DIR, MERGED_DIR
from src.utils.http import RateLimitedClient

CAMERAS_IMAGES_DIR = IMAGES_DIR / "cameras"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def _sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    s = re.sub(r'[<>:"/\\|?*]', '_', name)
    s = re.sub(r'[\s_]+', '_', s).strip('_.')
    return s[:200] if s else 'unknown'


def _ext_from_url(url: str) -> str:
    """Extract file extension from a URL, defaulting to .jpg."""
    path = url.split("?")[0].split("#")[0]
    match = re.search(r"\.(\w{2,5})$", path)
    if match:
        ext = match.group(1).lower()
        if ext in ("jpg", "jpeg", "png", "gif", "webp", "tif", "tiff"):
            return ext
    return "jpg"


async def _resolve_commons_url(client: RateLimitedClient, filename: str) -> str | None:
    """Resolve a Wikimedia Commons filename to a direct download URL."""
    params = {
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    try:
        resp = await client.get(COMMONS_API, params=params)
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            imageinfo = page.get("imageinfo", [])
            if imageinfo:
                return imageinfo[0].get("url")
    except Exception as e:
        print(f"  Failed to resolve Commons URL for {filename}: {e}")
    return None


def _extract_commons_filename(url: str) -> str | None:
    """Extract filename from a Commons URL like .../wiki/File:Something.jpg."""
    match = re.search(r"/wiki/File:(.+)$", url)
    if match:
        return unquote(match.group(1))
    return None


async def _search_commons_image(client: RateLimitedClient, query: str) -> str | None:
    """Search Wikimedia Commons for an image matching the query.

    Returns a direct image URL or None.
    """
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query} camera",
        "gsrnamespace": "6",  # File namespace
        "gsrlimit": "3",
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "format": "json",
    }
    try:
        resp = await client.get(COMMONS_API, params=params)
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return None

        # Pick the best image: prefer JPEG, reasonable size, skip icons/logos
        best_url = None
        best_score = -1
        for page in pages.values():
            title = page.get("title", "").lower()
            # Skip logos, icons, diagrams
            if any(kw in title for kw in ["logo", "icon", "diagram", "map", "flag", "coat"]):
                continue
            imageinfo = page.get("imageinfo", [])
            if not imageinfo:
                continue
            info = imageinfo[0]
            mime = info.get("mime", "")
            width = info.get("width", 0)
            height = info.get("height", 0)
            url = info.get("url", "")

            if not url or width < 100 or height < 100:
                continue

            # Score: prefer JPEG, moderate size
            score = 0
            if "jpeg" in mime:
                score += 10
            if 300 < width < 4000:
                score += 5
            if best_url is None or score > best_score:
                best_url = url
                best_score = score

        return best_url
    except Exception:
        return None


async def download_camera_images(max_per_camera: int = 10) -> dict:
    """Download images for all merged cameras.

    1. For cameras with Commons URLs: resolve and download
    2. For cameras without images: search Commons
    3. Skip placeholder/icon images
    """
    cameras_path = MERGED_DIR / "cameras.json"
    if not cameras_path.exists():
        print("No merged cameras file found at", cameras_path)
        return {"total": 0, "downloaded": 0, "skipped": 0, "failed": 0, "searched": 0}

    cameras = json.loads(cameras_path.read_text())
    stats = {"total": len(cameras), "downloaded": 0, "skipped": 0, "failed": 0, "searched": 0}

    CAMERAS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    async with RateLimitedClient(min_delay=1.0) as client:
        for i, camera in enumerate(cameras):
            camera_id = camera.get("id")
            name = camera.get("name", "unknown")
            mfr = camera.get("manufacturer_normalized", "")
            images = camera.get("images", [])

            if not camera_id:
                stats["skipped"] += 1
                continue

            # Filter out placeholder images
            real_images = [
                img for img in images
                if img.get("url") and "/icons/" not in img["url"]
            ]

            # If no real images, search Commons
            if not real_images:
                search_query = f"{mfr} {name}" if mfr else name
                commons_url = await _search_commons_image(client, search_query)
                stats["searched"] += 1
                if commons_url:
                    real_images = [{"url": commons_url, "source": "commons_search"}]
                    # Add to camera's images list
                    camera.setdefault("images", []).append({
                        "url": commons_url,
                        "source": "commons_search",
                        "license": "CC",
                    })
                else:
                    stats["skipped"] += 1
                    if (i + 1) % 500 == 0:
                        print(f"  [{i+1}/{len(cameras)}] Progress: {stats['downloaded']} downloaded, "
                              f"{stats['searched']} searched, {stats['skipped']} skipped")
                    continue

            # Download the first real image
            downloaded_count = 0
            for img in real_images[:max_per_camera]:
                url = img.get("url", "")
                if not url:
                    continue

                # Check if already downloaded
                if img.get("local_path"):
                    existing = Path(img["local_path"])
                    if existing.exists():
                        downloaded_count += 1
                        continue

                # Resolve Commons page URLs to direct download links
                download_url = url
                commons_filename = _extract_commons_filename(url)
                if commons_filename:
                    resolved = await _resolve_commons_url(client, commons_filename)
                    if resolved:
                        download_url = resolved
                    else:
                        stats["failed"] += 1
                        continue

                ext = _ext_from_url(download_url)
                safe_name = _sanitize_filename(f"{mfr}_{name}")
                dest = CAMERAS_IMAGES_DIR / f"{safe_name}.{ext}"
                if dest.exists() and img.get("local_path") != str(dest):
                    suffix = 2
                    while (CAMERAS_IMAGES_DIR / f"{safe_name}_{suffix}.{ext}").exists():
                        suffix += 1
                    dest = CAMERAS_IMAGES_DIR / f"{safe_name}_{suffix}.{ext}"

                success = await client.download_file(download_url, dest)

                if success:
                    img["local_path"] = str(dest.relative_to(Path(__file__).resolve().parent.parent.parent))
                    downloaded_count += 1
                    stats["downloaded"] += 1
                else:
                    stats["failed"] += 1

            if (i + 1) % 200 == 0:
                print(f"  [{i+1}/{len(cameras)}] Progress: {stats['downloaded']} downloaded, "
                      f"{stats['searched']} searched, {stats['failed']} failed")

    # Save updated cameras with local_path references
    cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"\nDone. Downloaded: {stats['downloaded']}, Searched: {stats['searched']}, "
          f"Skipped: {stats['skipped']}, Failed: {stats['failed']}")
    return stats


def main():
    """Entry point."""
    asyncio.run(download_camera_images())
