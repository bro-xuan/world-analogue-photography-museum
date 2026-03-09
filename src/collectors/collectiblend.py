"""Collect camera data from collectiblend.com."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.models.camera import Camera, ImageReference, SourceReference
from src.normalization.manufacturers import (
    get_manufacturer_country,
    normalize_manufacturer,
)
from src.patterns.digital import is_digital_name
from src.utils.data_io import save_records
from src.utils.http import RateLimitedClient

BASE_URL = "https://collectiblend.com"
CAMERAS_URL = f"{BASE_URL}/Cameras/"


def _parse_year_range(text: str) -> tuple[int | None, int | None]:
    """Extract year_introduced and year_discontinued from text like '1959' or '1959-1975'."""
    if not text:
        return None, None
    m = re.search(r"(\d{4})\s*[-–]\s*(\d{4})", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d{4})", text)
    if m:
        return int(m.group(1)), None
    return None, None


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------


def _parse_manufacturer_links(html: str) -> list[tuple[str, str]]:
    """Parse the main Cameras page to extract (manufacturer_name, url) pairs."""
    soup = BeautifulSoup(html, "lxml")
    links: list[tuple[str, str]] = []

    # Look for links that point to /Cameras/ManufacturerName/
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Match links like /Cameras/Canon/ or relative Canon/
        m = re.match(r"^(?:/Cameras/)?([A-Za-z0-9][^/]+)/$", href)
        if m:
            name = a_tag.get_text(strip=True)
            if not name:
                name = m.group(1)
            # Build absolute URL
            if href.startswith("/"):
                url = BASE_URL + href
            else:
                url = CAMERAS_URL + href
            links.append((name, url))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for name, url in links:
        if url not in seen:
            seen.add(url)
            unique.append((name, url))

    return unique


def _parse_camera_table(html: str, manufacturer_name: str) -> list[dict]:
    """Parse a manufacturer page to extract camera rows from the HTML table.

    Returns a list of dicts with keys: name, url, year_text, image_url, camera_type.
    """
    soup = BeautifulSoup(html, "lxml")
    cameras: list[dict] = []

    # Find the main camera table (typically the largest table on the page)
    tables = soup.find_all("table")
    if not tables:
        return cameras

    # Try each table looking for camera data
    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # Determine column indices from header row
        header_row = rows[0]
        headers = [th.get_text(strip=True).lower() for th in header_row.find_all(["th", "td"])]
        if not headers:
            continue

        # Map header names to column indices
        col_map: dict[str, int] = {}
        for idx, h in enumerate(headers):
            if "name" in h or "model" in h or "camera" in h:
                col_map["name"] = idx
            elif "year" in h or "date" in h or "introduced" in h or "produced" in h:
                col_map["year"] = idx
            elif "type" in h or "kind" in h or "category" in h:
                col_map["type"] = idx
            elif "image" in h or "photo" in h or "picture" in h or "thumb" in h:
                col_map["image"] = idx

        # If we can't find a name column, try the first text column
        if "name" not in col_map and headers:
            col_map["name"] = 0

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            # Extract camera name
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
                    camera_url = CAMERAS_URL + manufacturer_name + "/" + href

            if not camera_name or len(camera_name) < 2:
                continue

            # Extract year
            year_text = ""
            if "year" in col_map and col_map["year"] < len(cells):
                year_text = cells[col_map["year"]].get_text(strip=True)

            # Extract type
            camera_type = ""
            if "type" in col_map and col_map["type"] < len(cells):
                camera_type = cells[col_map["type"]].get_text(strip=True)

            # Construct image URL from camera detail page URL
            # Pattern: .../Cameras/AGFA/Agfaflex-I.html -> /Cameras/images/AGFA-Agfaflex-I.jpg
            image_url = None
            if camera_url and camera_url.startswith(BASE_URL + "/Cameras/"):
                path_part = camera_url[len(BASE_URL + "/Cameras/"):]  # "AGFA/Agfaflex-I.html"
                if path_part.endswith(".html"):
                    stem = path_part[:-5].replace("/", "-")  # "AGFA-Agfaflex-I"
                    image_url = f"{BASE_URL}/Cameras/images/{stem}.jpg"

            cameras.append({
                "name": camera_name,
                "url": camera_url,
                "year_text": year_text,
                "image_url": image_url,
                "camera_type": camera_type,
            })

    return cameras


# ---------------------------------------------------------------------------
# Collection logic
# ---------------------------------------------------------------------------


async def _collect() -> None:
    """Fetch all manufacturers and their cameras from collectiblend.com."""
    async with RateLimitedClient(min_delay=2.0) as client:
        print("=" * 60)
        print("COLLECTING CAMERAS FROM COLLECTIBLEND")
        print("=" * 60)

        # Step 1: Fetch main page to get manufacturer list
        print("Fetching manufacturer list...")
        try:
            resp = await client.get(CAMERAS_URL)
            manufacturer_links = _parse_manufacturer_links(resp.text)
        except Exception as e:
            print(f"Failed to fetch main page: {e}")
            return

        print(f"Found {len(manufacturer_links)} manufacturers.")

        all_cameras: list[Camera] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        total_skipped_digital = 0

        # Step 2: Iterate over each manufacturer
        for i, (mfr_name, mfr_url) in enumerate(manufacturer_links, 1):
            print(f"[{i}/{len(manufacturer_links)}] {mfr_name}...", end=" ")

            try:
                resp = await client.get(mfr_url)
            except Exception as e:
                print(f"SKIP (error: {e})")
                continue

            if resp.status_code == 404:
                print("SKIP (404)")
                continue

            camera_rows = _parse_camera_table(resp.text, mfr_name)
            manufacturer_norm = normalize_manufacturer(mfr_name)
            manufacturer_country = get_manufacturer_country(mfr_name)
            brand_cameras: list[Camera] = []

            for row in camera_rows:
                camera_name = row["name"]

                # Filter digital cameras
                if is_digital_name(camera_name):
                    total_skipped_digital += 1
                    continue

                year_intro, year_disc = _parse_year_range(row["year_text"])

                # Build image references
                images: list[ImageReference] = []
                if row.get("image_url"):
                    images.append(
                        ImageReference(
                            url=row["image_url"],
                            source="collectiblend",
                        )
                    )

                # Build source reference
                source_url = row.get("url") or mfr_url
                sources = [
                    SourceReference(
                        source="collectiblend",
                        source_url=source_url,
                        retrieved_at=now_iso,
                    )
                ]

                camera = Camera(
                    name=camera_name,
                    manufacturer=mfr_name,
                    manufacturer_normalized=manufacturer_norm,
                    manufacturer_country=manufacturer_country,
                    camera_type=row.get("camera_type") or None,
                    year_introduced=year_intro,
                    year_discontinued=year_disc,
                    images=images,
                    sources=sources,
                )
                brand_cameras.append(camera)

            all_cameras.extend(brand_cameras)
            print(f"{len(brand_cameras)} cameras")

        print(f"\nTotal cameras collected: {len(all_cameras)}")
        print(f"Digital cameras skipped: {total_skipped_digital}")

        save_records(all_cameras, source="collectiblend", entity_type="cameras")
        print("Collectiblend collection complete.")


def main() -> None:
    """Entry point for the Collectiblend collector."""
    asyncio.run(_collect())


if __name__ == "__main__":
    main()
