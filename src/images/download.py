"""Download images for cameras and films from all sources.

For cameras without images, searches multiple sources in waterfall order:
1. Wikidata P18 property
2. Wikimedia Commons search
3. Flickr CC-licensed images (Scrapling scraper, no API key)
4. Camera-wiki.org (Flickr embeds via HTML scraping)
5. Manufacturer museums (Canon, Nikon)
6. DuckDuckGo image search / eBay listings
7. Museum APIs (Smithsonian, Science Museum Group)
8. Google Custom Search (optional, requires API key)
"""

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import unquote

from src.images.camerawiki_search import search_camerawiki_images
from src.images.google_search import search_google_images
from src.images.manufacturer_museums import search_manufacturer_museum
from src.images.museum_search import search_museum_images
from src.images.web_search import search_ebay_images
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


async def _fetch_p18_image(client: RateLimitedClient, qid: str) -> str | None:
    """Fetch image URL from Wikidata P18 (image) property for a QID."""
    try:
        resp = await client.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetentities",
                "ids": qid,
                "props": "claims",
                "format": "json",
            },
        )
        data = resp.json()
        entity = data.get("entities", {}).get(qid, {})
        claims = entity.get("claims", {})
        p18 = claims.get("P18", [])
        if not p18:
            return None
        filename = p18[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        if not filename:
            return None
        # Resolve the Commons filename to a direct URL
        return await _resolve_commons_url(client, filename)
    except Exception:
        return None


def _pick_best_image(pages: dict, camera_name: str = "") -> str | None:
    """Pick the best image from a Commons API response, preferring JPEG and moderate size."""
    best_url = None
    best_score = -1
    name_lower = camera_name.lower()

    for page in pages.values():
        title = page.get("title", "").lower()
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

        score = 0
        if "jpeg" in mime:
            score += 10
        if 300 < width < 4000:
            score += 5
        # Boost if filename contains the camera name
        if name_lower and name_lower.replace(" ", "_") in title:
            score += 20
        if best_url is None or score > best_score:
            best_url = url
            best_score = score

    return best_url


async def _fetch_wikipedia_image(client: RateLimitedClient, wiki_url: str) -> str | None:
    """Fetch the main image from a Wikipedia article via the API."""
    match = re.search(r"wikipedia\.org/wiki/(.+?)(?:#.*)?$", wiki_url)
    if not match:
        return None
    title = unquote(match.group(1))
    try:
        resp = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": title,
                "prop": "pageimages",
                "piprop": "original",
                "format": "json",
            },
        )
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            original = page.get("original", {})
            url = original.get("source")
            if url:
                return url
    except Exception:
        pass
    return None


async def _search_commons_image(client: RateLimitedClient, query: str, camera_name: str = "") -> str | None:
    """Search Wikimedia Commons for an image matching the query.

    Tries exact phrase first, then falls back to keyword search.
    Returns a direct image URL or None.
    """
    # Try exact phrase match only (keyword fallback removed to reduce API calls)
    for search_query in [f'filetype:bitmap "{query}"']:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": search_query,
            "gsrnamespace": "6",  # File namespace
            "gsrlimit": "5",
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "format": "json",
        }
        try:
            resp = await client.get(COMMONS_API, params=params)
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            if pages:
                result = _pick_best_image(pages, camera_name)
                if result:
                    return result
        except Exception:
            continue
    return None


async def validate_image_urls(cameras: list[dict], client: RateLimitedClient) -> int:
    """HEAD-request existing image URLs, remove broken ones. Returns count removed."""
    removed = 0
    for i, camera in enumerate(cameras):
        images = camera.get("images", [])
        if not images:
            continue
        valid = []
        for img in images:
            url = img.get("url", "")
            if not url:
                continue
            # Skip Commons URLs (they're reliable) and local paths
            if "wikimedia.org" in url or "wikipedia.org" in url:
                valid.append(img)
                continue
            try:
                resp = await client.get(url)
                if resp.status_code < 400:
                    valid.append(img)
                else:
                    removed += 1
            except Exception:
                removed += 1
        camera["images"] = valid
        if (i + 1) % 1000 == 0:
            print(f"    Validated {i+1}/{len(cameras)} cameras ({removed} broken URLs removed)")
    return removed


def _strip_undownloaded_urls(cameras: list[dict]) -> int:
    """Remove image entries that have URLs but no local_path (i.e. download failed).

    This ensures Phase 2 search triggers for cameras whose URLs were broken.
    Preserves entries with local_path or commons/wikimedia URLs (reliable).
    """
    stripped = 0
    for camera in cameras:
        images = camera.get("images", [])
        if not images:
            continue
        kept = []
        for img in images:
            if img.get("local_path"):
                kept.append(img)
            elif img.get("url") and ("wikimedia.org" in img["url"] or "wikipedia.org" in img["url"]):
                kept.append(img)
            elif img.get("url"):
                stripped += 1
            # Drop entries with no url and no local_path
        camera["images"] = kept
    return stripped


async def download_camera_images(max_per_camera: int = 8, search_missing: bool = True) -> dict:
    """Download images for all merged cameras.

    Phase 1: Download from existing URLs (fast, collectiblend/chinesecamera/etc.)
    Phase 2: Search for missing images (slower, Commons/Flickr/Museum APIs)
    """
    cameras_path = MERGED_DIR / "cameras.json"
    if not cameras_path.exists():
        print("No merged cameras file found at", cameras_path)
        return {"total": 0, "downloaded": 0, "skipped": 0, "failed": 0, "searched": 0}

    cameras = json.loads(cameras_path.read_text())
    stats = {"total": len(cameras), "downloaded": 0, "skipped": 0, "failed": 0, "searched": 0,
             "already_local": 0}

    CAMERAS_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Pre-pass: match existing downloaded files back to cameras
    # Supports both old flat structure (mfr_name.jpg) and new folder structure (mfr/name/main.jpg)
    existing_flat = {f.name for f in CAMERAS_IMAGES_DIR.iterdir() if f.is_file()}
    matched = 0
    project_root = Path(__file__).resolve().parent.parent.parent
    for camera in cameras:
        if any(img.get("local_path") for img in camera.get("images", [])):
            continue  # Already linked
        mfr = camera.get("manufacturer_normalized", "")
        name = camera.get("name", "unknown")
        safe_mfr = _sanitize_filename(mfr) if mfr else "unknown"
        safe_name = _sanitize_filename(name)

        # Check new folder structure first
        camera_dir = CAMERAS_IMAGES_DIR / safe_mfr / safe_name
        if camera_dir.is_dir():
            files = sorted(camera_dir.iterdir())
            if files:
                rel_path = str(files[0].relative_to(project_root))
                images = camera.get("images", [])
                if images:
                    images[0]["local_path"] = rel_path
                else:
                    camera["images"] = [{"url": "", "source": "local", "local_path": rel_path}]
                matched += 1
                continue

        # Fall back to old flat structure
        old_name = _sanitize_filename(f"{mfr}_{name}")
        for ext in ("jpg", "jpeg", "png"):
            candidate = f"{old_name}.{ext}"
            if candidate in existing_flat:
                rel_path = str((CAMERAS_IMAGES_DIR / candidate).relative_to(project_root))
                images = camera.get("images", [])
                if images:
                    images[0]["local_path"] = rel_path
                else:
                    camera["images"] = [{"url": "", "source": "local", "local_path": rel_path}]
                matched += 1
                break
    if matched:
        print(f"  Matched {matched} existing local files to camera records", flush=True)
        stats["already_local"] = matched

    async with RateLimitedClient(min_delay=3.0, verify_ssl=False) as client:
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

            # Skip cameras that already have a local image
            has_local = any(img.get("local_path") for img in images)
            if has_local:
                continue

            # If no real images, try multiple search strategies (Phase 2)
            if not real_images and search_missing:
                commons_url = None
                stats["searched"] += 1

                # Try Camera-wiki.org (CC-licensed, multi-image)
                if not commons_url:
                    cwiki_results = await search_camerawiki_images(name, mfr, client, max_results=max_per_camera)
                    if cwiki_results:
                        commons_url = cwiki_results[0]["url"]
                        camera.setdefault("images", []).extend(cwiki_results)
                        real_images = cwiki_results

                # Try manufacturer museum sites (Canon, Nikon, etc.)
                if not commons_url:
                    museum_mfr_results = await search_manufacturer_museum(name, mfr, client, max_results=max_per_camera)
                    if museum_mfr_results:
                        commons_url = museum_mfr_results[0]["url"]
                        camera.setdefault("images", []).extend(museum_mfr_results)
                        real_images = museum_mfr_results

                # Try eBay
                if not commons_url:
                    ebay_results = await search_ebay_images(name, mfr, client, max_results=max_per_camera)
                    if ebay_results:
                        commons_url = ebay_results[0]["url"]
                        camera.setdefault("images", []).extend(ebay_results)
                        real_images = ebay_results

                # Try Museum APIs (Smithsonian, Science Museum)
                if not commons_url:
                    museum_results = await search_museum_images(name, mfr, client)
                    if museum_results:
                        commons_url = museum_results[0]["url"]
                        camera.setdefault("images", []).extend(museum_results)
                        real_images = museum_results

                # Try Google Custom Search (gap-filler, if API key configured)
                if not commons_url:
                    google_results = await search_google_images(name, mfr, client, max_results=max_per_camera)
                    if google_results:
                        commons_url = google_results[0]["url"]
                        camera.setdefault("images", []).extend(google_results)
                        real_images = google_results

                if commons_url and not real_images:
                    print(f"  Found image for {mfr} {name}", flush=True)
                    real_images = [{"url": commons_url, "source": "commons_search"}]
                    camera.setdefault("images", []).append({
                        "url": commons_url,
                        "source": "commons_search",
                        "license": "CC",
                    })

                if real_images:
                    print(f"  + {mfr} {name}: {len(real_images)} images found", flush=True)
                else:
                    stats["skipped"] += 1
                    continue

            # Download images into per-camera folder
            safe_mfr = _sanitize_filename(mfr) if mfr else "unknown"
            safe_camera = _sanitize_filename(name)
            camera_dir = CAMERAS_IMAGES_DIR / safe_mfr / safe_camera
            downloaded_count = 0

            for img_idx, img in enumerate(real_images[:max_per_camera]):
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
                filename = f"{img_idx + 1}.{ext}" if img_idx > 0 else f"main.{ext}"
                dest = camera_dir / filename

                # If file exists, just link it (don't re-download)
                if dest.exists():
                    img["local_path"] = str(dest.relative_to(Path(__file__).resolve().parent.parent.parent))
                    downloaded_count += 1
                    stats["already_local"] += 1
                    continue

                success = await client.download_file(download_url, dest)

                if success:
                    img["local_path"] = str(dest.relative_to(Path(__file__).resolve().parent.parent.parent))
                    downloaded_count += 1
                    stats["downloaded"] += 1
                else:
                    stats["failed"] += 1

            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(cameras)}] Progress: {stats['downloaded']} downloaded, "
                      f"{stats['searched']} searched, {stats['failed']} failed, "
                      f"{stats['already_local']} already local", flush=True)
            if (i + 1) % 50 == 0:
                # Periodic save to avoid losing progress
                cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))

    # Final save
    cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"\nDone. Downloaded: {stats['downloaded']}, Searched: {stats['searched']}, "
          f"Skipped: {stats['skipped']}, Failed: {stats['failed']}, "
          f"Already local: {stats['already_local']}", flush=True)
    return stats


def main():
    """Entry point: Phase 1 (download existing URLs), then Phase 2 (search for missing)."""
    import sys
    skip_search = "--no-search" in sys.argv
    search_only = "--search-only" in sys.argv

    if search_only:
        # Phase 2 only: strip broken URLs, then search for missing
        cameras_path = MERGED_DIR / "cameras.json"
        cameras = json.loads(cameras_path.read_text())
        stripped = _strip_undownloaded_urls(cameras)
        print(f"Stripped {stripped} broken URLs from camera records", flush=True)
        cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
        print("Phase 2: searching for missing images", flush=True)
        asyncio.run(download_camera_images(search_missing=True))
    elif skip_search:
        print("Phase 1 only: downloading from existing URLs (skipping search)", flush=True)
        asyncio.run(download_camera_images(search_missing=False))
    else:
        asyncio.run(download_camera_images(search_missing=True))
