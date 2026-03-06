"""Search museum open-access APIs for camera images.

Sources:
- Smithsonian Open Access (api.si.edu) — CC0 license
- Science Museum Group (collection.sciencemuseumgroup.org.uk) — CC-BY-NC-SA 4.0
"""

from __future__ import annotations

from src.utils.http import RateLimitedClient

SMITHSONIAN_API = "https://api.si.edu/openaccess/api/v1.0/search"
SMG_API = "https://collection.sciencemuseumgroup.org.uk/search"


async def search_smithsonian(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
) -> list[dict] | None:
    """Search Smithsonian Open Access for camera images.

    Returns list of {"url", "source", "license", "caption"} or None.
    No API key required.
    """
    query = f"{manufacturer} {camera_name} camera" if manufacturer else f"{camera_name} camera"

    params = {
        "q": query,
        "images": "true",
        "rows": "3",
        "start": "0",
    }

    try:
        resp = await client.get(SMITHSONIAN_API, params=params)
        data = resp.json()
        rows = data.get("response", {}).get("rows", [])
        if not rows:
            return None

        results = []
        for row in rows:
            content = row.get("content", {})
            descriptive = content.get("descriptiveNonRepeating", {})
            online_media = descriptive.get("online_media", {})
            media_items = online_media.get("media", [])

            title = content.get("freetext", {}).get("name", [{}])
            if isinstance(title, list) and title:
                title = title[0].get("content", "")
            elif isinstance(title, dict):
                title = title.get("content", "")

            for media in media_items:
                media_type = media.get("type", "")
                if "image" not in media_type.lower() and media_type != "Images":
                    continue
                url = media.get("content")
                if not url:
                    # Try thumbnail
                    url = media.get("thumbnail")
                if url:
                    results.append({
                        "url": url,
                        "source": "smithsonian",
                        "license": "CC0-1.0",
                        "caption": f"Smithsonian Open Access: {title}" if title else "Smithsonian Open Access",
                    })
                    break  # One image per row

        return results if results else None
    except Exception:
        return None


async def search_science_museum(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
) -> list[dict] | None:
    """Search Science Museum Group collection for camera images.

    Returns list of {"url", "source", "license", "caption"} or None.
    """
    query = f"{manufacturer} {camera_name}" if manufacturer else camera_name

    try:
        resp = await client.get(
            SMG_API,
            params={
                "q": query,
                "filter[has_image]": "true",
                "filter[categories]": "Cameras",
                "page[size]": "3",
            },
            headers={"Accept": "application/json"},
        )
        data = resp.json()
        items = data.get("data", [])
        if not items:
            return None

        results = []
        for item in items:
            attrs = item.get("attributes", {})
            multimedia = attrs.get("multimedia", [])
            title = attrs.get("summary_title", "")

            for media in multimedia:
                processed = media.get("processed", {})
                # Try medium or large size
                img_info = processed.get("medium", {}) or processed.get("large", {})
                url = img_info.get("location")
                if url:
                    if url.startswith("//"):
                        url = "https:" + url
                    results.append({
                        "url": url,
                        "source": "science_museum",
                        "license": "CC-BY-NC-SA-4.0",
                        "caption": f"Science Museum Group: {title}" if title else "Science Museum Group Collection",
                    })
                    break

        return results if results else None
    except Exception:
        return None


async def search_museum_images(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
) -> list[dict] | None:
    """Search all museum APIs for camera images. Returns first successful result."""
    # Try Smithsonian first (CC0 — best license)
    result = await search_smithsonian(camera_name, manufacturer, client)
    if result:
        return result

    # Fall back to Science Museum Group
    result = await search_science_museum(camera_name, manufacturer, client)
    if result:
        return result

    return None
