"""Collect camera data from camera-wiki.org via the MediaWiki API."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from src.models.camera import Camera, ImageReference, SourceReference
from src.normalization.manufacturers import get_manufacturer_country, normalize_manufacturer
from src.utils.data_io import save_records
from src.utils.http import RateLimitedClient

API_URL = "https://camera-wiki.org/api.php"
ARTICLE_BASE = "https://camera-wiki.org/wiki/"

# Categories that indicate a page is about a camera.
CAMERA_CATEGORY_KEYWORDS = {
    "slr cameras",
    "tlr cameras",
    "rangefinder cameras",
    "box cameras",
    "folding cameras",
    "medium format cameras",
    "large format cameras",
    "instant cameras",
    "35mm cameras",
    "126 cameras",
    "110 cameras",
    "aps cameras",
    "disc cameras",
    "japanese cameras",
    "german cameras",
    "soviet cameras",
    "chinese cameras",
}

# Map category keywords to camera_type values.
_CATEGORY_TYPE_MAP = {
    "slr": "SLR",
    "tlr": "TLR",
    "rangefinder": "Rangefinder",
    "box": "Box camera",
    "folding": "Folding",
    "instant": "Instant",
    "medium format": "Medium format",
    "large format": "View camera",
}

# Map category keywords to film_format values.
_CATEGORY_FORMAT_MAP = {
    "35mm": "35mm",
    "126": "126",
    "110": "110",
    "aps": "APS",
    "disc": "Disc",
    "medium format": "120",
    "large format": "Large format",
}


# ---------------------------------------------------------------------------
# Wikitext helpers (simplified from wikipedia.py)
# ---------------------------------------------------------------------------

def _clean_wikitext(value: str) -> str:
    """Strip common wikitext markup from a value string."""
    if not value:
        return value
    text = value
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', text)
    text = text.replace(']]', '').replace('[[', '')
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&ndash;', '-').replace('&mdash;', '-')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _parse_year(text: str) -> tuple[int | None, int | None]:
    """Extract year_introduced and year_discontinued from text."""
    if not text:
        return None, None
    cleaned = _clean_wikitext(text)
    m = re.search(r'(\d{4})\s*[-–]\s*(\d{4})', cleaned)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r'(\d{4})', cleaned)
    if m:
        return int(m.group(1)), None
    return None, None


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

async def _get_all_pages(client: RateLimitedClient) -> list[str]:
    """Enumerate ALL pages on camera-wiki.org via allpages, returning titles."""
    titles: list[str] = []
    params = {
        "action": "query",
        "list": "allpages",
        "aplimit": "500",
        "format": "json",
    }

    while True:
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        batch = data.get("query", {}).get("allpages", [])
        titles.extend(p["title"] for p in batch)
        cont = data.get("continue")
        if cont and "apcontinue" in cont:
            params["apcontinue"] = cont["apcontinue"]
            print(f"  Enumerated {len(titles)} pages so far...")
        else:
            break

    return titles


async def _get_categories(client: RateLimitedClient, titles: list[str]) -> dict[str, list[str]]:
    """Fetch categories for a batch of pages (up to 50 at a time).

    Returns {title: [category_title, ...]} mapping.
    """
    result: dict[str, list[str]] = {}

    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        params = {
            "action": "query",
            "titles": "|".join(batch),
            "prop": "categories",
            "cllimit": "500",
            "format": "json",
        }
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title", "")
            cats = page.get("categories", [])
            result[title] = [c["title"] for c in cats]

    return result


def _is_camera_page(categories: list[str]) -> bool:
    """Check if a page's categories indicate it's about a camera."""
    for cat in categories:
        cat_lower = cat.lower().replace("category:", "")
        # Exact match against known camera categories
        if cat_lower in CAMERA_CATEGORY_KEYWORDS:
            return True
        # Fuzzy: any category containing "camera"
        if "camera" in cat_lower:
            return True
    return False


def _camera_type_from_categories(categories: list[str]) -> str | None:
    """Infer camera type from category names."""
    for cat in categories:
        cat_lower = cat.lower().replace("category:", "")
        for keyword, cam_type in _CATEGORY_TYPE_MAP.items():
            if keyword in cat_lower:
                return cam_type
    return None


def _film_format_from_categories(categories: list[str]) -> str | None:
    """Infer film format from category names."""
    for cat in categories:
        cat_lower = cat.lower().replace("category:", "")
        for keyword, fmt in _CATEGORY_FORMAT_MAP.items():
            if keyword in cat_lower:
                return fmt
    return None


async def _get_page_wikitext(client: RateLimitedClient, title: str) -> str | None:
    """Fetch wikitext for a single page."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
    }
    try:
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        return data.get("parse", {}).get("wikitext", {}).get("*")
    except Exception as e:
        print(f"  Failed to fetch wikitext for '{title}': {e}")
        return None


async def _get_page_images(client: RateLimitedClient, title: str) -> list[str]:
    """Fetch image filenames used on a page."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "images",
        "format": "json",
    }
    try:
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        return data.get("parse", {}).get("images", [])
    except Exception:
        return []


async def _get_image_url(client: RateLimitedClient, filename: str) -> str | None:
    """Get the actual image URL for a File: page via imageinfo."""
    params = {
        "action": "query",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    try:
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            imageinfo = page.get("imageinfo", [])
            if imageinfo:
                return imageinfo[0].get("url")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Content parsing
# ---------------------------------------------------------------------------

_MANUFACTURER_PATTERNS = [
    re.compile(r'(?:made|manufactured|produced|built)\s+by\s+\[\[([^\]|]+)', re.IGNORECASE),
    re.compile(r'(?:made|manufactured|produced|built)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', re.IGNORECASE),
    re.compile(r"is\s+an?\s+\[\[([^\]|]+)\]\]", re.IGNORECASE),
]


def _parse_manufacturer_from_text(wikitext: str, title: str) -> str:
    """Try to extract manufacturer from the first paragraph of wikitext."""
    # Get first paragraph (before first section heading)
    first_para = wikitext.split("\n==")[0] if "\n==" in wikitext else wikitext
    # Only look at the first few lines
    lines = [l.strip() for l in first_para.split("\n") if l.strip() and not l.strip().startswith(("{", "|", "!", "[["[:2] + "File"))]
    first_sentence = " ".join(lines[:5])

    # Try explicit "made by" patterns
    for pattern in _MANUFACTURER_PATTERNS:
        m = pattern.search(first_sentence)
        if m:
            candidate = _clean_wikitext(m.group(1)).strip()
            # Validate it looks like a manufacturer name
            if candidate and len(candidate) < 50 and not candidate.lower().startswith(("camera", "lens", "the")):
                return candidate

    # Fall back: first word of title (e.g. "Nikon F3" -> "Nikon")
    parts = title.split()
    if len(parts) >= 2:
        return parts[0]
    return title


def _extract_infobox(wikitext: str) -> dict[str, str]:
    """Extract key-value pairs from an infobox-like template in wikitext."""
    # Camera-wiki.org uses various infobox templates
    match = re.search(r'\{\{\s*(?:Infobox|Camera)[^}]*\|', wikitext, re.IGNORECASE)
    if not match:
        return {}

    start = match.start()
    depth = 0
    i = start
    end = len(wikitext)
    while i < end:
        if wikitext[i:i + 2] == '{{':
            depth += 1
            i += 2
        elif wikitext[i:i + 2] == '}}':
            depth -= 1
            if depth == 0:
                i += 2
                break
            i += 2
        else:
            i += 1

    infobox_text = wikitext[start:i]
    params: dict[str, str] = {}
    lines = re.split(r'\n\s*\|', infobox_text)
    for line in lines:
        if '=' in line:
            key, _, val = line.partition('=')
            key = key.strip().lower()
            val = val.strip()
            val = re.sub(r'\}\}\s*$', '', val).strip()
            if key and not key.startswith('{'):
                params[key] = val

    return params


def _parse_year_from_content(wikitext: str) -> tuple[int | None, int | None]:
    """Try to extract year from wikitext content (infobox or first paragraph)."""
    # Try infobox fields first
    params = _extract_infobox(wikitext)
    for field in ("produced", "year", "intro_year", "production", "date"):
        if field in params:
            y_intro, y_disc = _parse_year(params[field])
            if y_intro:
                return y_intro, y_disc

    # Try first paragraph
    first_para = wikitext.split("\n==")[0] if "\n==" in wikitext else wikitext
    # Look for patterns like "introduced in 1959" or "from 1959"
    m = re.search(r'(?:introduced|released|launched|produced|made|from)\s+(?:in\s+)?(\d{4})', first_para, re.IGNORECASE)
    if m:
        year = int(m.group(1))
        if 1800 <= year <= 2030:
            return year, None

    # Any 4-digit year in the first paragraph
    years = [int(y) for y in re.findall(r'\b(1[89]\d{2}|20[0-2]\d)\b', first_para)]
    if years:
        return min(years), None

    return None, None


def _parse_format_from_content(wikitext: str) -> str | None:
    """Try to extract film format from infobox or content."""
    params = _extract_infobox(wikitext)
    for field in ("film_format", "film_size", "format", "film"):
        if field in params:
            cleaned = _clean_wikitext(params[field])
            if cleaned:
                return cleaned

    # Search content for common formats
    first_para = wikitext.split("\n==")[0] if "\n==" in wikitext else wikitext
    format_patterns = [
        (r'\b35\s*mm\b', "35mm"),
        (r'\b120\s*film\b', "120"),
        (r'\b120/220\b', "120"),
        (r'\b6x[46789]\b', "120"),
        (r'\b6\s*[x×]\s*[46789]', "120"),
        (r'\b4\s*[x×]\s*5', "4x5"),
        (r'\b127\s*film\b', "127"),
        (r'\b126\s*(?:film|cartridge)\b', "126"),
        (r'\b110\s*(?:film|cartridge)\b', "110"),
        (r'\binstant\s*film\b', "Instant"),
        (r'\bAPS\b', "APS"),
        (r'\bdisc\s*film\b', "Disc"),
    ]
    for pattern, fmt in format_patterns:
        if re.search(pattern, first_para, re.IGNORECASE):
            return fmt

    return None


def _parse_lens_mount_from_content(wikitext: str) -> str | None:
    """Try to extract lens mount from infobox."""
    params = _extract_infobox(wikitext)
    for field in ("lens_mount", "mount"):
        if field in params:
            cleaned = _clean_wikitext(params[field])
            if cleaned:
                return cleaned
    return None


def _article_url(title: str) -> str:
    return ARTICLE_BASE + title.replace(" ", "_")


# ---------------------------------------------------------------------------
# Main collection logic
# ---------------------------------------------------------------------------

async def _collect() -> None:
    """Run the camera-wiki.org collection pipeline."""
    async with RateLimitedClient(min_delay=4.0) as client:
        # Step 1: Enumerate all pages
        print("=" * 60)
        print("COLLECTING CAMERAS FROM CAMERA-WIKI.ORG")
        print("=" * 60)
        print("Enumerating all pages...")
        all_titles = await _get_all_pages(client)
        print(f"Found {len(all_titles)} total pages")

        # Step 2: Check categories in batches to find camera pages
        print("\nFetching categories for all pages...")
        title_categories = await _get_categories(client, all_titles)
        print(f"Fetched categories for {len(title_categories)} pages")

        camera_titles: list[str] = []
        camera_categories_map: dict[str, list[str]] = {}
        for title, cats in title_categories.items():
            if _is_camera_page(cats):
                camera_titles.append(title)
                camera_categories_map[title] = cats

        print(f"Identified {len(camera_titles)} camera pages")

        # Step 3: Fetch wikitext and images for each camera page
        cameras: list[Camera] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for idx, title in enumerate(camera_titles):
            if (idx + 1) % 100 == 0:
                print(f"  Processing {idx + 1}/{len(camera_titles)}...")

            wikitext = await _get_page_wikitext(client, title)
            if not wikitext:
                continue

            categories = camera_categories_map.get(title, [])

            # Parse fields
            manufacturer_raw = _parse_manufacturer_from_text(wikitext, title)
            manufacturer_norm = normalize_manufacturer(manufacturer_raw)
            manufacturer_country = get_manufacturer_country(manufacturer_raw)
            camera_type = _camera_type_from_categories(categories)
            film_format = _film_format_from_categories(categories) or _parse_format_from_content(wikitext)
            year_intro, year_disc = _parse_year_from_content(wikitext)
            lens_mount = _parse_lens_mount_from_content(wikitext)

            # Get images
            image_filenames = await _get_page_images(client, title)
            images: list[ImageReference] = []
            # Only process image files (skip icons, svgs, etc.)
            image_exts = (".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff")
            photo_filenames = [
                f for f in image_filenames
                if f.lower().endswith(image_exts)
            ]
            for filename in photo_filenames[:3]:  # Limit to 3 images per page
                url = await _get_image_url(client, filename)
                if url:
                    images.append(ImageReference(
                        url=url,
                        source="camerawiki",
                        caption=_clean_wikitext(filename.rsplit(".", 1)[0].replace("_", " ")),
                    ))

            camera = Camera(
                name=title,
                manufacturer=manufacturer_raw,
                manufacturer_normalized=manufacturer_norm,
                manufacturer_country=manufacturer_country,
                camera_type=camera_type,
                film_format=film_format,
                year_introduced=year_intro,
                year_discontinued=year_disc,
                lens_mount=lens_mount,
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
            if (idx + 1) % 100 == 0 or idx < 5:
                print(f"    + {camera.name} ({camera.manufacturer})")

        print(f"\nTotal cameras collected: {len(cameras)}")
        save_records(cameras, source="camerawiki", entity_type="cameras")
        print("\nCamera-wiki.org collection complete.")


def main() -> None:
    """Entry point for the camera-wiki.org collector."""
    asyncio.run(_collect())


if __name__ == "__main__":
    main()
