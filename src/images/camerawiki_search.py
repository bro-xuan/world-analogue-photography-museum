"""Search camera-wiki.org for additional camera images.

Camera-wiki.org pages embed Flickr photos directly as external URLs.
The MediaWiki images API doesn't report these — we need to parse the rendered
HTML to extract the actual image URLs (Flickr static CDN links).
"""

from __future__ import annotations

import re

from src.utils.http import RateLimitedClient

API_URL = "https://camera-wiki.org/api.php"
WIKI_BASE = "https://camera-wiki.org/wiki/"

# Pattern to extract Flickr image URLs from camera-wiki HTML
_FLICKR_IMG_RE = re.compile(
    r'(https?://(?:farm\d+\.static\.flickr\.com|live\.staticflickr\.com|'
    r'farm\d+\.staticflickr\.com|c\d+\.staticflickr\.com)/[^"\'>\s]+\.(?:jpg|jpeg|png))',
    re.IGNORECASE,
)

# Skip UI/license images
_SKIP_URL_PATTERNS = re.compile(
    r"(gnu-fdl|poweredby|mediawiki|/resources/|/skins/|logo|icon|badge|button)",
    re.IGNORECASE,
)

# Flickr size suffixes — upgrade to medium/large for better quality
# _q = 150x150 square, _m = 240, _n = 320, _z = 640, _c = 800, _b = 1024
_FLICKR_SIZE_RE = re.compile(r"_([sqtmnzcbo])\.(?:jpg|jpeg|png)$", re.IGNORECASE)


def _upgrade_flickr_url(url: str) -> str:
    """Upgrade a Flickr image URL to medium/large size if it's a thumbnail."""
    # Replace small size suffixes with _z (640px) for good quality
    if _FLICKR_SIZE_RE.search(url):
        current_suffix = _FLICKR_SIZE_RE.search(url).group(1)
        if current_suffix in ("s", "q", "t", "m", "n"):
            return _FLICKR_SIZE_RE.sub("_z.jpg", url)
    return url


async def _search_page(client: RateLimitedClient, query: str) -> str | None:
    """Search camera-wiki.org for a page matching the query. Returns page title or None."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": "3",
        "format": "json",
    }
    try:
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        results = data.get("query", {}).get("search", [])
        if results:
            return results[0]["title"]
    except Exception:
        pass
    return None


async def _get_page_html(client: RateLimitedClient, title: str) -> str | None:
    """Fetch the rendered HTML of a camera-wiki page."""
    url = WIKI_BASE + title.replace(" ", "_")
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def _extract_image_urls(html: str) -> list[str]:
    """Extract unique Flickr image URLs from the FIRST section of a camera-wiki page.

    Wiki pages often show the target camera in the intro/first section, then
    related or comparison cameras further down. We only take images before
    the first <h2> heading to avoid pulling wrong camera photos.
    """
    # Only look at the intro section (before first <h2> or "See also"/"Notes")
    # This is where the target camera's photos live.
    first_section = html
    h2_match = re.search(r'<h2[>\s]', html)
    if h2_match:
        first_section = html[:h2_match.start()]

    urls = _FLICKR_IMG_RE.findall(first_section)
    if not urls:
        return []

    # Deduplicate and filter
    seen_bases = set()
    result = []
    for url in urls:
        if _SKIP_URL_PATTERNS.search(url):
            continue

        # Upgrade to better quality
        url = _upgrade_flickr_url(url)

        # Deduplicate by Flickr photo ID (the numeric part before size suffix)
        # e.g., https://farm1.static.flickr.com/95/281049981_91621fa71d.jpg
        base_match = re.search(r"/(\d+_[a-f0-9]+)", url)
        if base_match:
            base_id = base_match.group(1)
            if base_id in seen_bases:
                continue
            seen_bases.add(base_id)

        result.append(url)

    return result


async def search_camerawiki_images(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
    max_results: int = 3,
) -> list[dict] | None:
    """Search camera-wiki.org for images of a camera.

    Fetches the wiki page and extracts embedded Flickr image URLs.
    Only pulls from the intro section (before first <h2>) to avoid
    picking up photos of related/comparison cameras.

    Returns list of {"url", "source", "license", "caption"} or None.
    """
    # Build candidate page titles (try direct page first, then search)
    candidates = []
    if manufacturer and not camera_name.lower().startswith(manufacturer.lower()):
        candidates.append(f"{manufacturer} {camera_name}")
    candidates.append(camera_name)

    # Try direct page load first (avoids search returning wrong pages like
    # "Canon EOS 7" when we want "Canon 7")
    html = None
    page_title = None
    for title in candidates:
        html = await _get_page_html(client, title)
        if html:
            page_title = title
            break

    # Fall back to search API if direct load failed
    if not html:
        for query in candidates:
            page_title = await _search_page(client, query)
            if page_title:
                html = await _get_page_html(client, page_title)
                if html:
                    break

    if not html:
        return None
    if not html:
        return None

    image_urls = _extract_image_urls(html)
    if not image_urls:
        return None

    results = []
    for url in image_urls[:max_results]:
        results.append({
            "url": url,
            "source": "camerawiki",
            "license": "CC",
            "caption": f"Camera-wiki.org: {page_title}",
        })

    return results if results else None
