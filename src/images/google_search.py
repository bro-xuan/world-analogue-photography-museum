"""Search Google Custom Search API for camera images.

Requires environment variables:
- GOOGLE_API_KEY: Google Cloud API key with Custom Search JSON API enabled
- GOOGLE_CSE_ID: Programmable Search Engine ID (configured for image search)

Free tier: 100 queries/day. Paid: $5 per 1000 queries.
"""

from __future__ import annotations

import os

from src.utils.http import RateLimitedClient

SEARCH_URL = "https://customsearch.googleapis.com/customsearch/v1"


async def search_google_images(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
    max_results: int = 5,
) -> list[dict] | None:
    """Search Google Custom Search for camera images.

    Returns list of {"url", "source", "license", "caption"} or None.
    Requires GOOGLE_API_KEY and GOOGLE_CSE_ID environment variables.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        return None

    # Build search query
    if manufacturer and not camera_name.lower().startswith(manufacturer.lower()):
        query = f"{manufacturer} {camera_name} camera"
    else:
        query = f"{camera_name} camera"

    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "searchType": "image",
        "num": str(min(max_results, 10)),
        "imgSize": "medium",
        "safe": "active",
    }

    try:
        resp = await client.get(SEARCH_URL, params=params)
        if resp.status_code != 200:
            return None

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None

        results = []
        for item in items:
            url = item.get("link", "")
            title = item.get("title", "")
            image_info = item.get("image", {})
            width = image_info.get("width", 0)
            height = image_info.get("height", 0)

            if not url:
                continue

            # Skip tiny images
            if width < 150 or height < 150:
                continue

            # Skip known bad patterns
            if any(skip in url.lower() for skip in ["logo", "icon", "banner", "avatar", "sprite"]):
                continue

            results.append({
                "url": url,
                "source": "google",
                "license": "unknown",
                "caption": f"Google: {title}" if title else "Google image search",
            })

            if len(results) >= max_results:
                break

        return results if results else None
    except Exception as e:
        print(f"  Google search failed for {query}: {e}", flush=True)
        return None
