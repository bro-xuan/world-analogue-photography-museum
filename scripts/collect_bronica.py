#!/usr/bin/env python3
"""Collect Bronica camera data from collectiblend.com detail pages.

Scrapes all Bronica (Zenza) models from collectiblend, extracting descriptions,
market prices, specs, and images. Saves raw data, downloads images, and merges
into the existing cameras.json.
"""

import asyncio
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

from bs4 import BeautifulSoup

from src.models.camera import Camera, ImageReference, SourceReference
from src.normalization.manufacturers import get_manufacturer_country, normalize_manufacturer
from src.pricing.collectiblend_prices import _parse_market_price
from src.utils.data_io import DATA_DIR, IMAGES_DIR, MERGED_DIR, save_records
from src.utils.http import RateLimitedClient

BASE_URL = "https://collectiblend.com"
MANUFACTURER_PAGE = f"{BASE_URL}/Cameras/Zenza/"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_camera_links(html: str) -> list[dict]:
    """Parse the Zenza manufacturer page to extract camera detail page URLs.

    Returns a list of dicts with keys: name, url, year_text, camera_type, image_url.
    """
    soup = BeautifulSoup(html, "lxml")
    cameras: list[dict] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Determine column indices from header row
        header_row = rows[0]
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]
        if not headers:
            continue

        col_map: dict[str, int] = {}
        for idx, h in enumerate(headers):
            if "name" in h or "model" in h or "camera" in h:
                col_map["name"] = idx
            elif "year" in h or "date" in h or "introduced" in h or "produced" in h:
                col_map["year"] = idx
            elif "type" in h or "kind" in h or "category" in h:
                col_map["type"] = idx

        if "name" not in col_map and headers:
            col_map["name"] = 0

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            name_idx = col_map.get("name", 0)
            if name_idx >= len(cells):
                continue
            name_cell = cells[name_idx]
            name_link = name_cell.find("a")
            camera_name = name_cell.get_text(strip=True)
            camera_url = None
            if name_link and name_link.get("href"):
                href = name_link["href"]
                if href.startswith("/"):
                    camera_url = BASE_URL + href
                elif href.startswith("http"):
                    camera_url = href
                else:
                    camera_url = f"{BASE_URL}/Cameras/Zenza/{href}"

            if not camera_name or len(camera_name) < 2:
                continue

            year_text = ""
            if "year" in col_map and col_map["year"] < len(cells):
                year_text = cells[col_map["year"]].get_text(strip=True)

            camera_type = ""
            if "type" in col_map and col_map["type"] < len(cells):
                camera_type = cells[col_map["type"]].get_text(strip=True)

            # Image URL pattern: /Cameras/images/Zenza-{Model}.jpg
            image_url = None
            if camera_url and camera_url.endswith(".html"):
                path_part = camera_url[len(BASE_URL + "/Cameras/"):]
                if "/" in path_part:
                    stem = path_part[:-5].replace("/", "-")
                    image_url = f"{BASE_URL}/Cameras/images/{stem}.jpg"

            cameras.append({
                "name": camera_name,
                "url": camera_url,
                "year_text": year_text,
                "camera_type": camera_type,
                "image_url": image_url,
            })

    return cameras


def _parse_year_range(text: str) -> tuple[int | None, int | None]:
    """Extract year_introduced and year_discontinued from text."""
    if not text:
        return None, None
    m = re.search(r"(\d{4})\s*[-–]\s*(\d{4})", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d{4})", text)
    if m:
        return int(m.group(1)), None
    return None, None


def _extract_detail_data(html: str) -> dict:
    """Extract rich data from a collectiblend camera detail page.

    Returns dict with: description, market_price, year, film_format, camera_type.
    """
    soup = BeautifulSoup(html, "lxml")
    data: dict = {}

    # Market price
    price = _parse_market_price(html)
    if price and price > 0:
        data["market_price"] = price

    # Description from meta description tag
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        data["description"] = meta_desc["content"].strip()

    # If no meta description, try first substantial paragraph
    if not data.get("description"):
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 40:
                data["description"] = text
                break

    # Extract year from description text
    desc = data.get("description", "")
    if desc:
        m = re.search(r"\b(19\d{2}|20[0-2]\d)\b", desc)
        if m:
            data["year"] = int(m.group(1))

    # Extract film format from description
    if re.search(r"\b120\s*film\b|\b120\b.*\bfilm\b", desc, re.I):
        data["film_format"] = "120"
    elif re.search(r"\b6\s*[x×]\s*[4-7]\.?\d?\s*cm\b", desc, re.I):
        data["film_format"] = "120"
    elif re.search(r"\b220\b", desc, re.I):
        data["film_format"] = "120"
    elif re.search(r"\b35\s*mm\b|\b135\b", desc, re.I):
        data["film_format"] = "135"

    # Extract camera type from description
    if re.search(r"\bSLR\b", desc):
        data["camera_type_detail"] = "SLR"
    elif re.search(r"\brangefinder\b", desc, re.I):
        data["camera_type_detail"] = "Rangefinder"

    return data


# ---------------------------------------------------------------------------
# Main collection logic
# ---------------------------------------------------------------------------


async def collect_bronica() -> list[Camera]:
    """Scrape all Bronica cameras from collectiblend.com."""
    now_iso = datetime.now(timezone.utc).isoformat()
    manufacturer_norm = normalize_manufacturer("Zenza")
    manufacturer_country = get_manufacturer_country("Zenza")

    async with RateLimitedClient(min_delay=2.0) as client:
        print("=" * 60)
        print("COLLECTING BRONICA CAMERAS FROM COLLECTIBLEND")
        print("=" * 60)

        # Step 1: Fetch manufacturer page to get camera list
        print(f"Fetching {MANUFACTURER_PAGE}...")
        try:
            resp = await client.get(MANUFACTURER_PAGE)
        except Exception as e:
            print(f"Failed to fetch manufacturer page: {e}")
            return []

        camera_rows = _parse_camera_links(resp.text)
        print(f"Found {len(camera_rows)} cameras on listing page")

        # Step 2: Visit each detail page for rich data
        cameras: list[Camera] = []
        for i, row in enumerate(camera_rows, 1):
            camera_name = row["name"]
            detail_url = row.get("url")
            year_intro, year_disc = _parse_year_range(row["year_text"])

            print(f"  [{i}/{len(camera_rows)}] {camera_name}...", end=" ", flush=True)

            detail_data: dict = {}
            if detail_url:
                try:
                    resp = await client.get(detail_url)
                    detail_data = _extract_detail_data(resp.text)
                    print(f"price=${detail_data.get('market_price', '-')}", end=" ", flush=True)
                except Exception as e:
                    print(f"(detail error: {e})", end=" ", flush=True)

            # Prefer detail page year over listing year
            if detail_data.get("year") and not year_intro:
                year_intro = detail_data["year"]

            # Camera type: prefer listing page, fallback to detail
            camera_type = row.get("camera_type") or detail_data.get("camera_type_detail") or None

            # Film format from detail page (all Bronica are 120, but let's extract it)
            film_format = detail_data.get("film_format") or "120"

            # Build image reference
            images: list[ImageReference] = []
            if row.get("image_url"):
                images.append(
                    ImageReference(
                        url=row["image_url"],
                        source="collectiblend",
                        is_hosted=True,
                    )
                )

            # Build source reference
            sources = [
                SourceReference(
                    source="collectiblend",
                    source_url=detail_url or MANUFACTURER_PAGE,
                    retrieved_at=now_iso,
                )
            ]

            camera = Camera(
                name=camera_name,
                manufacturer="Zenza",
                manufacturer_normalized=manufacturer_norm,
                manufacturer_country=manufacturer_country,
                camera_type=camera_type if camera_type else None,
                film_format=film_format,
                year_introduced=year_intro,
                year_discontinued=year_disc,
                price_market_usd=detail_data.get("market_price"),
                price_market_source="collectiblend" if detail_data.get("market_price") else None,
                description=detail_data.get("description"),
                images=images,
                sources=sources,
            )
            cameras.append(camera)
            print("OK")

        print(f"\nCollected {len(cameras)} Bronica cameras")
        prices_found = sum(1 for c in cameras if c.price_market_usd)
        print(f"Market prices found: {prices_found}/{len(cameras)}")

        # Step 3: Download images
        print("\nDownloading images...")
        downloaded = 0
        for cam in cameras:
            for img in cam.images:
                # Build local path: data/images/cameras/Bronica/Bronica_{Model}/main.jpg
                model_name = cam.name.replace(" ", "_").replace("/", "-")
                local_dir = IMAGES_DIR / "cameras" / "Bronica" / f"Bronica_{model_name}"
                local_path = local_dir / "main.jpg"

                # Use relative path (data/images/...) for portability
                rel_path = str(local_path.relative_to(DATA_DIR.parent))

                if local_path.exists():
                    print(f"  [skip] {cam.name} (already exists)")
                    img.local_path = rel_path
                    downloaded += 1
                    continue

                success = await client.download_file(img.url, local_path)
                if success:
                    img.local_path = rel_path
                    downloaded += 1
                    print(f"  [ok] {cam.name}")
                else:
                    print(f"  [fail] {cam.name}: {img.url}")

        print(f"Downloaded {downloaded}/{len(cameras)} images")

        return cameras


def _merge_into_cameras_json(bronica_cameras: list[Camera]) -> None:
    """Merge Bronica cameras into data/merged/cameras.json.

    Loads existing merged data if present, removes any existing Bronica entries,
    then adds the new ones. Creates the file if it doesn't exist.
    """
    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    cameras_path = MERGED_DIR / "cameras.json"

    existing: list[dict] = []
    if cameras_path.exists():
        existing = json.loads(cameras_path.read_text())
        print(f"Loaded {len(existing)} existing cameras from {cameras_path}")

    # Remove existing Bronica entries
    before = len(existing)
    existing = [
        c for c in existing
        if (c.get("manufacturer_normalized") or "").lower() != "bronica"
    ]
    removed = before - len(existing)
    if removed:
        print(f"Removed {removed} existing Bronica entries")

    # Convert new cameras to dicts and assign IDs
    new_records = []
    for cam in bronica_cameras:
        record = cam.model_dump(exclude_none=True)
        record["id"] = str(uuid.uuid4())
        if not record.get("launch_date") and record.get("year_introduced"):
            record["launch_date"] = str(record["year_introduced"])
        new_records.append(record)

    existing.extend(new_records)

    cameras_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print(f"Saved {len(existing)} cameras to {cameras_path} ({len(new_records)} Bronica)")


async def _main() -> None:
    cameras = await collect_bronica()
    if not cameras:
        print("No cameras collected!")
        return

    # Save raw data
    save_records(cameras, source="collectiblend_bronica", entity_type="cameras")

    # Merge into cameras.json
    print("\n" + "=" * 60)
    print("MERGING INTO CAMERAS.JSON")
    print("=" * 60)
    _merge_into_cameras_json(cameras)

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)
    print(f"\nNext steps:")
    print(f"  1. uv run python scripts/enrich_descriptions.py     # Wikipedia descriptions")
    print(f"  2. uv run python scripts/enrich_descriptions_web.py  # Web search descriptions")
    print(f"  3. uv run python scripts/enrich_prices.py            # Launch prices")
    print(f"  4. uv run python scripts/generate_thumbnails.py      # Thumbnails")
    print(f"  5. uv run python scripts/prepare_landing_data.py     # Landing page data")
    print(f"  6. uv run python scripts/prepare_brands_data.py      # Brand pages")
    print(f"  7. uv run python scripts/prepare_camera_pages.py     # Camera detail pages")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
