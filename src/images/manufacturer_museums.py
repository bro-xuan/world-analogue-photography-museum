"""Search manufacturer museum/archive websites for official camera product photos.

Supported museums:
- Canon Camera Museum (global.canon/en/c-museum/) — 251+ film cameras with product shots

Product pages use predictable URLs:
- Thumbnail: /ja/c-museum/wp-content/uploads/2015/05/film{N}_s.jpg
- Full size:  /ja/c-museum/wp-content/uploads/2015/05/film{N}_b.jpg
"""

from __future__ import annotations

import re

from src.utils.http import RateLimitedClient

_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

CANON_INDEX_URL = "https://global.canon/en/c-museum/camera.html?s=film"
CANON_IMAGE_BASE = "https://global.canon/ja/c-museum/wp-content/uploads/2015/05"

# Cache the Canon index to avoid re-fetching per camera
_canon_index_cache: list[tuple[str, str]] | None = None


def _normalize(name: str) -> str:
    """Lowercase, strip non-alphanumeric for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


async def _load_canon_index(client: RateLimitedClient) -> list[tuple[str, str]]:
    """Load the Canon Museum film camera index. Returns [(name, product_id), ...]."""
    global _canon_index_cache
    if _canon_index_cache is not None:
        return _canon_index_cache

    try:
        resp = await client.get(CANON_INDEX_URL, headers=_BROWSER_HEADERS)
        if resp.status_code != 200:
            _canon_index_cache = []
            return []

        # Extract: product ID and camera name
        # Pattern: product/film{N}.html ... <span class="en">{Name}</span>
        # Each product_box has the product link and name
        pattern = re.compile(
            r'href="/en/c-museum/product/(film\d+)\.html".*?'
            r'<span class="en">([^<]+)</span>',
            re.DOTALL,
        )

        entries = []
        seen_ids = set()
        for match in pattern.finditer(resp.text):
            product_id = match.group(1)
            name = match.group(2).strip()
            if product_id not in seen_ids:
                seen_ids.add(product_id)
                entries.append((name, product_id))

        _canon_index_cache = entries
        return entries
    except Exception:
        _canon_index_cache = []
        return []


def _match_canon_camera(
    camera_name: str, index: list[tuple[str, str]]
) -> str | None:
    """Find the best matching Canon product ID for a camera name."""
    # Strip "Canon" prefix for matching
    search_name = camera_name
    if search_name.lower().startswith("canon"):
        search_name = search_name[5:].strip()

    search_norm = _normalize(search_name)
    if not search_norm:
        return None

    # Try exact match first
    for name, product_id in index:
        if _normalize(name) == search_norm:
            return product_id

    # Try substring match (search name contained in canon name or vice versa)
    for name, product_id in index:
        canon_norm = _normalize(name)
        if search_norm in canon_norm or canon_norm in search_norm:
            return product_id

    return None


async def _search_canon_museum(
    camera_name: str,
    client: RateLimitedClient,
    max_results: int = 5,
) -> list[dict] | None:
    """Search Canon Camera Museum for product photos."""
    index = await _load_canon_index(client)
    if not index:
        return None

    product_id = _match_canon_camera(camera_name, index)
    if not product_id:
        return None

    # Canon product images use predictable URLs
    # _b = big/full image, _s = small thumbnail
    image_url = f"{CANON_IMAGE_BASE}/{product_id}_b.jpg"

    # Verify the image exists
    try:
        resp = await client.get(image_url, headers=_BROWSER_HEADERS)
        if resp.status_code != 200:
            return None
    except Exception:
        return None

    return [{
        "url": image_url,
        "source": "canon_museum",
        "license": "manufacturer",
        "caption": f"Canon Camera Museum: {camera_name}",
    }]


# Map manufacturer names to their museum search functions
_MUSEUM_SCRAPERS = {
    "canon": _search_canon_museum,
}


async def search_manufacturer_museum(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
    max_results: int = 5,
) -> list[dict] | None:
    """Search manufacturer museum sites for product photos.

    Only attempts search for manufacturers with known museum sites.
    Returns list of {"url", "source", "license", "caption"} or None.
    """
    mfr_lower = manufacturer.lower().strip()
    scraper = _MUSEUM_SCRAPERS.get(mfr_lower)
    if not scraper:
        return None

    return await scraper(camera_name, client, max_results)
