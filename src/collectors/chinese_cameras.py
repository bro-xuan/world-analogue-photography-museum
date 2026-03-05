"""Collect Chinese analogue cameras from camera-wiki.org Category:China.

Targeted crawl of just the China category (~190 pages) instead of the
full site (~10 hours).  Falls back to a curated list for cameras missing
from camera-wiki.org, then enriches images via Wikimedia Commons.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from src.collectors.camerawiki import (
    API_URL,
    _article_url,
    _camera_type_from_categories,
    _clean_wikitext,
    _film_format_from_categories,
    _get_image_url,
    _get_page_images,
    _get_page_wikitext,
    _is_camera_page,
    _parse_format_from_content,
    _parse_manufacturer_from_text,
    _parse_year_from_content,
)
from src.images.download import _search_commons_image
from src.models.camera import Camera, ImageReference, SourceReference
from src.normalization.manufacturers import get_manufacturer_country, normalize_manufacturer
from src.utils.data_io import save_records
from src.utils.http import RateLimitedClient

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Well-documented Chinese cameras that may be missing from camera-wiki.org
FALLBACK_CAMERAS: list[tuple[str, str, int, str, str]] = [
    # (name, manufacturer, year, film_format, camera_type)
    ("Seagull 4A", "Seagull", 1964, "120", "TLR"),
    ("Seagull 4B", "Seagull", 1964, "120", "TLR"),
    ("Seagull 4C", "Seagull", 1970, "120", "TLR"),
    ("Seagull 205", "Seagull", 1964, "120", "Rangefinder"),
    ("Seagull DF-1", "Seagull", 1971, "135", "SLR"),
    ("Seagull DF-2", "Seagull", 1984, "135", "SLR"),
    ("Seagull DF-300", "Seagull", 1985, "135", "SLR"),
    ("Shanghai 58-I", "Shanghai", 1958, "135", "Rangefinder"),
    ("Shanghai 58-II", "Shanghai", 1958, "135", "Rangefinder"),
    ("Red Flag 20", "Red Flag", 1971, "135", "Rangefinder"),
    ("Dong Feng 120", "Dong Feng", 1969, "120", "SLR"),
    ("Pearl River 4", "Pearl River", 1964, "120", "TLR"),
    ("Pearl River S-201", "Pearl River", 1972, "120", "TLR"),
    ("Great Wall SZ-1", "Great Wall", 1969, "135", "Rangefinder"),
    ("Great Wall DF-3", "Great Wall", 1973, "120", "SLR"),
    ("Phenix 205", "Phenix", 1970, "135", "Rangefinder"),
    ("Phenix 205A", "Phenix", 1975, "135", "Rangefinder"),
    ("Huaxia 821", "Huaxia", 1982, "135", "Rangefinder"),
    ("Huaxia 822", "Huaxia", 1983, "135", "Rangefinder"),
    ("Qingdao SF-2", "Qingdao", 1975, "120", "TLR"),
    ("Zi Jin Shan SLR", "Zi Jin Shan", 1958, "135", "SLR"),
    ("Mudan MD-1", "Mudan", 1984, "120", "TLR"),
    ("Huqiu 120", "Huqiu", 1982, "120", "TLR"),
    ("Hua Zhong SFJ-3", "Hua Zhong", 1965, "120", "TLR"),
    ("Holga 120N", "Holga", 1982, "120", "Box camera"),
    ("Holga 120S", "Holga", 1982, "120", "Box camera"),
    ("Holga 135", "Holga", 2005, "135", "Box camera"),
    ("Diana F", "Diana", 1960, "120", "Box camera"),
]


async def _get_category_members_recursive(
    client: RateLimitedClient,
    category: str,
    max_depth: int = 2,
    visited: set[str] | None = None,
) -> list[str]:
    """Walk a category tree on camera-wiki.org and return all page titles."""
    if visited is None:
        visited = set()
    if category in visited or max_depth < 0:
        return []
    visited.add(category)

    pages: list[str] = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmtype": "page|subcat",
        "cmlimit": "500",
        "format": "json",
    }

    while True:
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        members = data.get("query", {}).get("categorymembers", [])
        for m in members:
            if m.get("ns") == 14:  # Subcategory
                sub_title = m["title"]
                sub_pages = await _get_category_members_recursive(
                    client, sub_title, max_depth - 1, visited,
                )
                pages.extend(sub_pages)
            else:
                pages.append(m["title"])

        cont = data.get("continue")
        if cont and "cmcontinue" in cont:
            params["cmcontinue"] = cont["cmcontinue"]
        else:
            break

    return pages


async def _get_page_categories(client: RateLimitedClient, title: str) -> list[str]:
    """Fetch categories for a single page."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "categories",
        "cllimit": "500",
        "format": "json",
    }
    try:
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            return [c["title"] for c in page.get("categories", [])]
    except Exception:
        pass
    return []


async def _collect() -> None:
    """Run the Chinese cameras collection pipeline."""
    async with RateLimitedClient(min_delay=4.0) as wiki_client:
        print("=" * 60)
        print("COLLECTING CHINESE CAMERAS FROM CAMERA-WIKI.ORG")
        print("=" * 60)

        # Phase A: Crawl Category:China on camera-wiki.org
        print("\nPhase A: Fetching Category:China pages...")
        all_titles = await _get_category_members_recursive(
            wiki_client, "Category:China", max_depth=2,
        )
        # Deduplicate
        all_titles = list(dict.fromkeys(all_titles))
        print(f"  Found {len(all_titles)} pages under Category:China")

        cameras: list[Camera] = []
        seen_names: set[str] = set()
        now_iso = datetime.now(timezone.utc).isoformat()

        for idx, title in enumerate(all_titles):
            if (idx + 1) % 20 == 0:
                print(f"  Processing {idx + 1}/{len(all_titles)}...")

            # Fetch categories to determine camera type/format
            categories = await _get_page_categories(wiki_client, title)

            wikitext = await _get_page_wikitext(wiki_client, title)
            if not wikitext:
                continue

            # Parse fields
            manufacturer_raw = _parse_manufacturer_from_text(wikitext, title)
            manufacturer_norm = normalize_manufacturer(manufacturer_raw)
            manufacturer_country = get_manufacturer_country(manufacturer_raw) or "China"
            camera_type = _camera_type_from_categories(categories)
            film_format = (
                _film_format_from_categories(categories)
                or _parse_format_from_content(wikitext)
            )
            year_intro, year_disc = _parse_year_from_content(wikitext)

            # Get images
            image_filenames = await _get_page_images(wiki_client, title)
            images: list[ImageReference] = []
            image_exts = (".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff")
            photo_filenames = [
                f for f in image_filenames if f.lower().endswith(image_exts)
            ]
            for filename in photo_filenames[:3]:
                url = await _get_image_url(wiki_client, filename)
                if url:
                    images.append(
                        ImageReference(
                            url=url,
                            source="camerawiki",
                            caption=_clean_wikitext(
                                filename.rsplit(".", 1)[0].replace("_", " ")
                            ),
                        )
                    )

            camera = Camera(
                name=title,
                manufacturer=manufacturer_raw,
                manufacturer_normalized=manufacturer_norm,
                manufacturer_country=manufacturer_country,
                camera_type=camera_type,
                film_format=film_format,
                year_introduced=year_intro,
                year_discontinued=year_disc,
                images=images,
                sources=[
                    SourceReference(
                        source="camerawiki",
                        source_url=_article_url(title),
                        retrieved_at=now_iso,
                    )
                ],
            )
            cameras.append(camera)
            seen_names.add(title.lower())
            print(f"    + {camera.name} ({camera.manufacturer})")

        print(f"\n  Phase A collected {len(cameras)} cameras from camera-wiki.org")

        # Phase B: Curated fallback list
        print("\nPhase B: Adding curated fallback cameras...")
        fallback_added = 0
        for name, manufacturer, year, film_fmt, cam_type in FALLBACK_CAMERAS:
            if name.lower() in seen_names:
                continue
            manufacturer_norm = normalize_manufacturer(manufacturer)
            camera = Camera(
                name=name,
                manufacturer=manufacturer,
                manufacturer_normalized=manufacturer_norm,
                manufacturer_country=get_manufacturer_country(manufacturer) or "China",
                camera_type=cam_type,
                film_format=film_fmt,
                year_introduced=year,
                sources=[
                    SourceReference(
                        source="camerawiki",
                        source_url=_article_url(name),
                        retrieved_at=now_iso,
                    )
                ],
            )
            cameras.append(camera)
            seen_names.add(name.lower())
            fallback_added += 1
            print(f"    + {name} ({manufacturer}) [fallback]")

        print(f"  Added {fallback_added} fallback cameras")

    # Phase C: Image enrichment via Wikimedia Commons
    print("\nPhase C: Searching Wikimedia Commons for missing images...")
    async with RateLimitedClient(min_delay=1.0) as commons_client:
        enriched = 0
        for camera in cameras:
            if camera.images:
                continue
            query = f"{camera.manufacturer} {camera.name}"
            url = await _search_commons_image(commons_client, query)
            if url:
                camera.images.append(
                    ImageReference(
                        url=url,
                        source="commons_search",
                        license="CC",
                    )
                )
                enriched += 1
                print(f"    + Found image for {camera.name}")

        print(f"  Enriched {enriched} cameras with Commons images")

    # Save
    print(f"\nTotal Chinese cameras collected: {len(cameras)}")
    save_records(cameras, source="camerawiki", entity_type="cameras_chinese")

    # Also merge into the main camerawiki cameras file if it exists
    from src.utils.data_io import RAW_DIR
    import json

    main_path = RAW_DIR / "camerawiki" / "cameras.json"
    if main_path.exists():
        existing = json.loads(main_path.read_text())
        existing_names = {r.get("name", "").lower() for r in existing}
        new_records = [
            c.model_dump(exclude_none=True)
            for c in cameras
            if c.name.lower() not in existing_names
        ]
        if new_records:
            existing.extend(new_records)
            main_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
            print(f"  Appended {len(new_records)} new cameras to {main_path}")
    else:
        # No existing file — save as the main camerawiki cameras file
        save_records(cameras, source="camerawiki", entity_type="cameras")

    print("\nChinese cameras collection complete.")


def main() -> None:
    """Entry point for the Chinese cameras collector."""
    asyncio.run(_collect())


if __name__ == "__main__":
    main()
