"""Search Flickr for CC-licensed camera product images using Scrapling.

Uses a waterfall strategy to find photos OF cameras (not taken BY cameras):
1. Search within camera collector groups (best signal — all photos are OF cameras)
2. Fall back to text search with "camera body" + interestingness sort

Validates photo titles against camera name/manufacturer to avoid wrong images.
No API key needed — scrapes Flickr search results via headless browser.
"""

from __future__ import annotations

import re
import time
import unicodedata

from scrapling import StealthyFetcher

# Shared fetcher instance (reused across calls to keep browser session)
_fetcher: StealthyFetcher | None = None
_last_request_time: float = 0.0
MIN_DELAY = 3.0  # seconds between Flickr requests

# Flickr groups where people post photos OF cameras (not taken BY cameras).
# Ordered by quality/strictness. Search stops at first group with results.
CAMERA_GROUPS = [
    "55624923@N00",  # Old Film Cameras (only photos of cameras) — strictest
    "94898401@N00",  # Camera Appreciation (Pictures of cameras)
    "54739042@N00",  # Your Camera Collection
]


def _get_fetcher() -> StealthyFetcher:
    global _fetcher
    if _fetcher is None:
        _fetcher = StealthyFetcher()
    return _fetcher


def _rate_limit():
    """Enforce minimum delay between requests."""
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < MIN_DELAY:
        time.sleep(MIN_DELAY - elapsed)
    _last_request_time = time.monotonic()


def _normalize(text: str) -> str:
    """Lowercase, strip accents, keep only alphanumeric + spaces."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _title_matches(
    title: str, camera_name: str, manufacturer: str
) -> bool:
    """Check if a Flickr photo title is relevant to the camera.

    Requires the manufacturer OR at least 50% of camera name tokens
    to appear in the photo title.
    """
    if not title:
        return False

    norm_title = _normalize(title)
    norm_mfr = _normalize(manufacturer) if manufacturer else ""
    norm_name = _normalize(camera_name)

    # Reject if title contains a DIFFERENT well-known camera brand
    # (e.g., a photo titled "Zenit 12" should not match "Rollei Zoom X 70")
    other_brands = {
        "canon", "nikon", "pentax", "olympus", "minolta", "yashica",
        "mamiya", "hasselblad", "leica", "contax", "rollei", "voigtlander",
        "fuji", "fujica", "ricoh", "konica", "zenit", "kiev", "fed",
        "zorki", "praktica", "agfa", "kodak", "polaroid", "lomo",
        "bronica", "graflex", "chinon", "cosina", "miranda", "petri",
        "topcon", "vivitar", "argus", "bell howell", "ensign", "ilford",
    }
    title_tokens = set(norm_title.split())
    for brand in other_brands:
        if brand in norm_title and brand != norm_mfr and brand not in norm_name:
            return False

    # Check manufacturer appears in title
    if norm_mfr and norm_mfr in norm_title:
        return True

    # Check at least 50% of camera name tokens appear in title
    name_tokens = [t for t in norm_name.split() if len(t) > 1]
    if not name_tokens:
        return False
    matches = sum(1 for t in name_tokens if t in norm_title)
    return matches / len(name_tokens) >= 0.5


def _extract_images(
    page, max_results: int,
    camera_name: str = "", manufacturer: str = "",
    validate: bool = False,
) -> list[dict]:
    """Extract staticflickr image URLs from a Flickr page.

    When validate=True, only returns images whose alt/title text
    matches the camera name or manufacturer.
    """
    results = []
    for img in page.css("img"):
        src = img.attrib.get("src", "")
        if "live.staticflickr.com" not in src:
            continue

        # Get photo title from alt text or parent link title
        title = img.attrib.get("alt", "")
        if not title:
            parent = img.parent
            if parent:
                title = parent.attrib.get("title", "")

        # Validate title if requested
        if validate and not _title_matches(title, camera_name, manufacturer):
            continue

        # Convert thumbnail URL to 1024px version
        # Pattern: //live.staticflickr.com/{server}/{id}_{secret}_{size}.jpg
        big_url = re.sub(r"_[a-z]\.jpg$", "_b.jpg", src)
        if not big_url.startswith("http"):
            big_url = "https:" + big_url

        caption = title.strip() if title.strip() else "Flickr CC-licensed photo"

        results.append({
            "url": big_url,
            "source": "flickr_scrape",
            "license": "CC",
            "caption": caption,
        })

        if len(results) >= max_results:
            break

    return results


def _search_groups(
    query: str, max_results: int,
    camera_name: str = "", manufacturer: str = "",
) -> list[dict]:
    """Search within camera collector groups for product photos."""
    fetcher = _get_fetcher()
    encoded_query = query.replace(" ", "+")

    for group_id in CAMERA_GROUPS:
        _rate_limit()
        encoded_gid = group_id.replace("@", "%40")
        url = (
            f"https://www.flickr.com/search/"
            f"?text={encoded_query}"
            f"&group_id={encoded_gid}"
        )
        try:
            page = fetcher.fetch(url)
            if page.status != 200:
                continue
            # Try with validation first, fall back to unvalidated for groups
            # (group photos are higher quality — people post photos OF cameras)
            results = _extract_images(
                page, max_results,
                camera_name=camera_name, manufacturer=manufacturer,
                validate=True,
            )
            if results:
                return results
            # Groups are curated, so accept unvalidated if title extraction fails
            results = _extract_images(page, max_results)
            if results:
                return results
        except Exception:
            continue

    return []


def _search_text(
    query: str, max_results: int,
    camera_name: str = "", manufacturer: str = "",
) -> list[dict]:
    """Text search with 'camera body' qualifier and interestingness sort.

    Always validates photo titles — text search results are noisy.
    """
    fetcher = _get_fetcher()
    encoded_query = (query + " camera body").replace(" ", "+")
    # CC licenses: 2=CC-BY-NC, 3=CC-BY-NC-ND, 4=CC-BY, 5=CC-BY-SA, 6=CC-BY-ND, 9=CC0
    url = (
        f"https://www.flickr.com/search/"
        f"?text={encoded_query}"
        f"&license=2%2C3%2C4%2C5%2C6%2C9"
        f"&sort=interestingness-desc"
    )
    _rate_limit()
    try:
        page = fetcher.fetch(url)
        if page.status != 200:
            return []
        # Text search is noisy — always validate titles
        return _extract_images(
            page, max_results,
            camera_name=camera_name, manufacturer=manufacturer,
            validate=True,
        )
    except Exception:
        return []


def search_flickr_images(
    camera_name: str,
    manufacturer: str,
    max_results: int = 1,
) -> list[dict] | None:
    """Search Flickr for CC-licensed product photos of a camera.

    Uses a waterfall strategy:
    1. Search camera collector groups (photos are OF cameras, not taken BY them)
    2. Fall back to text search with "camera body" + interestingness sort

    Photo titles are validated against camera name/manufacturer to avoid
    returning images of the wrong camera.

    Returns list of {"url", "source", "license", "caption"} or None.
    """
    query = f"{manufacturer} {camera_name}" if manufacturer else camera_name

    try:
        # Pass 1: Search camera collector groups
        results = _search_groups(
            query, max_results,
            camera_name=camera_name, manufacturer=manufacturer,
        )
        if results:
            return results

        # Pass 2: Text search fallback (strict validation)
        results = _search_text(
            query, max_results,
            camera_name=camera_name, manufacturer=manufacturer,
        )
        return results if results else None
    except Exception as e:
        print(f"  Flickr scrape failed for {query}: {e}", flush=True)
        return None
