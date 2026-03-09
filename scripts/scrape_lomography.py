"""Scrape Lomography shop for analogue cameras and add to cameras.json.

Fetches the listing page, then each product detail page for all gallery images.
Each edition (color variant) is treated as a separate camera model.

Usage:
    uv run python scripts/scrape_lomography.py --dry-run
    uv run python scripts/scrape_lomography.py --execute
"""

import argparse
import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, ".")

from src.utils.data_io import MERGED_DIR
from src.utils.http import RateLimitedClient

CAMERAS_IMAGES = Path("data/images/cameras")
CAMERAS_JSON = MERGED_DIR / "cameras.json"
LISTING_URL = "https://shop.lomography.com/eu/cameras/all"

# Film format detection from product name / URL
FORMAT_RULES = [
    (re.compile(r"\b110\b"), "110"),
    (re.compile(r"\b120\b|medium.format|6x6|lc-a.120", re.I), "120"),
    (re.compile(r"\bdiana\s+f\+|diana\s+multi\s+pinhole|diana\s+mini", re.I), "120"),
    (re.compile(r"\bfisheye.baby\b", re.I), "110"),
    (re.compile(r"\b35\s*mm\b|135|sprocket|fisheye.no|actionsampler|lomoapparat|lomourette|lc-wide|mc-a|la.sardina|lomokino|konstruktor|spinner|simple.use|lomomod", re.I), "135"),
]

# Keywords in filenames that indicate non-camera-body images
SKIP_KEYWORDS = [
    "packaging", "content-packaging", "combo-packaging",
    "uv-filter", "color-filter", "lens-cap", "splitzer",
    "easy-wrap", "handstrap", "leather-strap", "case",
    "lcd-screen",
]

# Sample photos (taken WITH the camera) have date-prefixed filenames
SAMPLE_PHOTO_RE = re.compile(r"/\d{4}-\d{2}-\d{2}[_]", re.I)


def _sanitize_filename(name: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', "_", name)
    s = re.sub(r"[\s_]+", "_", s).strip("_.")
    return s[:200] if s else "unknown"


def _detect_film_format(name: str, url: str) -> str:
    text = f"{name} {url}"
    for pattern, fmt in FORMAT_RULES:
        if pattern.search(text):
            return fmt
    return "135"  # default for Lomography


def _is_camera_image(url: str) -> bool:
    """Filter out accessory/packaging/sample images, keep camera body shots."""
    url_lower = url.lower()
    if any(kw in url_lower for kw in SKIP_KEYWORDS):
        return False
    if SAMPLE_PHOTO_RE.search(url_lower):
        return False
    return True


def scrape_listing(html: str) -> list[dict]:
    """Parse the listing page and extract all camera products."""
    soup = BeautifulSoup(html, "lxml")
    products = []

    for item in soup.select(".product-item"):
        link_el = item.select_one("a.product-item-link")
        if not link_el:
            continue

        # Text may have mangled whitespace from HTML (e.g. "MC-A35 mmFilm")
        name = " ".join(link_el.get_text(strip=True).split())
        detail_url = link_el.get("href", "")

        # Get listing thumbnail
        img_el = item.select_one("img")
        thumb_url = (img_el.get("src", "") or img_el.get("data-src", "")) if img_el else ""

        products.append({
            "name": name,
            "detail_url": detail_url,
            "thumb_url": thumb_url,
        })

    return products


def scrape_product_images(html: str) -> list[str]:
    """Extract gallery image URLs from a product detail page.

    Looks for the initialImages JSON array in the page's inline JS.
    Uses the 'full' resolution URL for each image.
    """
    # Look for initialImages JSON in inline scripts
    match = re.search(r'"initialImages"\s*:\s*(\[.*?\])\s*[,}]', html)
    if match:
        try:
            images = json.loads(match.group(1))
            urls = []
            for img in images:
                url = img.get("full") or img.get("img") or ""
                if url and url not in urls:
                    urls.append(url)
            return urls
        except json.JSONDecodeError:
            pass

    # Fallback: find CDN image URLs in the page
    return list(dict.fromkeys(
        re.findall(r'https://cdn\.shop\.lomography\.com/media/catalog/product/cache/[^"\\]+\.(?:jpg|png)', html)
    ))


# Skip products matching these patterns (bundles, accessories, not standalone cameras)
SKIP_PATTERNS = [
    re.compile(r"\bfilm\s+bundle\b", re.I),
    re.compile(r"\bscan\s+bundle\b", re.I),
    re.compile(r"\bgift\s+bundle\b", re.I),
    re.compile(r"\btry\s+them\s+all\b", re.I),
    re.compile(r"\bpool\s+party\s+bundle\b", re.I),
    re.compile(r"\bwedding\s+bundle\b", re.I),
    re.compile(r"\blovebug\s+bundle\b", re.I),
    re.compile(r"\blens\s+set\b", re.I),
    re.compile(r"\bunderwater\s+case\b", re.I),
    re.compile(r"\bmetropolis\s+film\s+bundle\b", re.I),
]


def should_skip(name: str) -> bool:
    """Return True if this product is a bundle/accessory, not a camera."""
    return any(p.search(name) for p in SKIP_PATTERNS)


def clean_product_name(raw_name: str) -> str:
    """Clean up product name for use as camera model name."""
    # First fix the mangled whitespace from HTML (e.g. "MC-A35 mmFilm Camera")
    name = raw_name.strip()
    # Fix "35 mm" stuck to preceding text
    name = re.sub(r"(\S)(35\s*mm)", r"\1 \2", name)
    # Remove "35 mm" + anything up to the edition name
    name = re.sub(r"\s+35\s*mm\s*\w*\s*(Camera\s*)?", " ", name, flags=re.I)
    name = re.sub(r"\s+Film\s+Camera\b", "", name, flags=re.I)
    name = re.sub(r"\s+Camera\s*&\s*Flash\b", "", name, flags=re.I)
    name = re.sub(r"\s+Camera\s+", " ", name, flags=re.I)
    name = re.sub(r"\s+Camera$", "", name, flags=re.I)
    name = re.sub(r"\s+Glass\s+Lens\s+Camera\b", "", name, flags=re.I)
    name = re.sub(r"\s+Glass\s+Lens$", "", name, flags=re.I)
    # Remove "& 12 mm lens" for Diana Baby
    name = re.sub(r"\s+&\s+12\s*mm\s+lens\b", "", name, flags=re.I)
    # Remove "& Flash" for Diana Mini
    name = re.sub(r"\s+&\s+Flash\b", "", name, flags=re.I)
    # Clean up "Half-frame & Square" suffix
    name = re.sub(r"\s+Half-frame\s+&\s+Square\b", "", name, flags=re.I)
    # Remove "Panoramic" suffix
    name = re.sub(r"\s+Panoramic$", "", name, flags=re.I)
    # Clean double spaces
    name = re.sub(r"\s+", " ", name).strip()
    return name


def make_description(name: str, film_format: str) -> str:
    """Generate a short description for a Lomography camera."""
    fmt_name = {"135": "35 mm", "110": "110", "120": "120 medium format"}.get(film_format, film_format)
    return f"The {name} is a {fmt_name} film camera produced by Lomography."


async def run(dry_run: bool):
    cameras = json.loads(CAMERAS_JSON.read_text())
    print(f"Loaded {len(cameras)} cameras")

    # Find existing Lomography shop entries
    existing_urls = set()
    for cam in cameras:
        for src in cam.get("sources", []):
            if src.get("source") == "lomography_shop":
                existing_urls.add(src.get("source_url", ""))

    async with RateLimitedClient(min_delay=1.0, verify_ssl=False) as client:
        # Step 1: Fetch listing page
        print("Fetching listing page...")
        resp = await client.get(LISTING_URL)
        products = scrape_listing(resp.text)
        print(f"Found {len(products)} products on listing page")

        # Step 2: Fetch each product detail page for images
        new_cameras = []
        for i, prod in enumerate(products):
            detail_url = prod["detail_url"]

            if detail_url in existing_urls:
                print(f"  [{i+1}/{len(products)}] SKIP (exists): {prod['name']}")
                continue

            if should_skip(prod["name"]):
                print(f"  [{i+1}/{len(products)}] SKIP (bundle): {prod['name']}")
                continue

            name = clean_product_name(prod["name"])
            film_format = _detect_film_format(prod["name"], detail_url)

            print(f"  [{i+1}/{len(products)}] Fetching: {name}")

            try:
                resp = await client.get(detail_url)
                all_images = scrape_product_images(resp.text)
            except Exception as e:
                print(f"    ERROR fetching {detail_url}: {e}")
                all_images = []

            # Filter to camera-body images only
            camera_images = [url for url in all_images if _is_camera_image(url)]
            if not camera_images and prod["thumb_url"]:
                camera_images = [prod["thumb_url"]]

            print(f"    {len(camera_images)} camera images (of {len(all_images)} total)")

            image_entries = []
            for url in camera_images:
                image_entries.append({
                    "url": url,
                    "source": "lomography_shop",
                    "license": "Product image",
                    "caption": "Lomography shop product image",
                    "local_path": None,
                })

            entry = {
                "name": name,
                "manufacturer": "Lomographische AG",
                "manufacturer_normalized": "Lomography",
                "manufacturer_country": "Austria",
                "images": image_entries,
                "sources": [{
                    "source": "lomography_shop",
                    "source_url": detail_url,
                    "retrieved_at": "2026-03-07T00:00:00+00:00",
                }],
                "id": str(uuid.uuid4()),
                "film_format": film_format,
                "description": make_description(name, film_format),
            }
            new_cameras.append(entry)

    # Deduplicate by cleaned name (keep the one with more images)
    seen: dict[str, dict] = {}
    for cam in new_cameras:
        key = cam["name"].lower()
        if key not in seen or len(cam["images"]) > len(seen[key]["images"]):
            seen[key] = cam
    new_cameras = list(seen.values())

    print(f"\nNew cameras (after dedup): {len(new_cameras)}")
    for cam in new_cameras:
        n_img = len(cam["images"])
        print(f"  {cam['name']:50s} | {cam['film_format']} | {n_img} images")

    if dry_run:
        print(f"\n[DRY RUN] No changes made.")
        return

    # Step 3: Download all images
    print(f"\nDownloading images...")
    total_dl = 0
    async with RateLimitedClient(min_delay=0.3, verify_ssl=False) as client:
        for cam in new_cameras:
            safe_mfr = _sanitize_filename(cam["manufacturer_normalized"])
            safe_name = _sanitize_filename(cam["name"])

            for img_idx, img in enumerate(cam["images"]):
                url = img["url"]
                ext = "png" if ".png" in url.lower() else "jpg"
                filename = f"main.{ext}" if img_idx == 0 else f"{img_idx + 1}.{ext}"
                dest = CAMERAS_IMAGES / safe_mfr / safe_name / filename

                if dest.exists():
                    img["local_path"] = str(dest)
                    total_dl += 1
                    continue

                success = await client.download_file(url, dest)
                if success:
                    img["local_path"] = str(dest)
                    total_dl += 1
                else:
                    print(f"    FAILED: {url}")

            downloaded_count = sum(1 for img in cam["images"] if img.get("local_path"))
            print(f"  {cam['name']}: {downloaded_count}/{len(cam['images'])} images")

    print(f"Total images downloaded: {total_dl}")

    # Step 4: Add to cameras.json
    cameras.extend(new_cameras)
    CAMERAS_JSON.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"\nSaved {len(cameras)} cameras to {CAMERAS_JSON}")

    # Verify
    lomo_count = sum(1 for c in cameras if c.get("manufacturer_normalized") == "Lomography")
    lomo_with_img = sum(
        1 for c in cameras
        if c.get("manufacturer_normalized") == "Lomography"
        and any(img.get("local_path") for img in c.get("images", []))
    )
    print(f"\n=== Verification ===")
    print(f"  Total Lomography cameras: {lomo_count}")
    print(f"  With images: {lomo_with_img}")


def main():
    parser = argparse.ArgumentParser(description="Scrape Lomography shop cameras")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview what would be added")
    group.add_argument("--execute", action="store_true", help="Scrape, download, and add")
    args = parser.parse_args()
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
