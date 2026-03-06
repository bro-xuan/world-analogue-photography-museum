"""Search Flickr for CC-licensed camera images.

Uses the Flickr public API (requires FLICKR_API_KEY env var).
Searches for photos *of* cameras (not taken *with* cameras) by targeting
camera collector groups and specific tags.
"""

from __future__ import annotations

import os

from src.utils.http import RateLimitedClient

FLICKR_API = "https://www.flickr.com/services/rest/"

# CC license IDs on Flickr
# 1=CC-BY-NC-SA, 2=CC-BY-NC, 3=CC-BY-NC-ND, 4=CC-BY, 5=CC-BY-SA, 6=CC-BY-ND,
# 9=CC0, 10=PDM
CC_LICENSES = "1,2,3,4,5,6,9,10"

# Flickr groups focused on camera collecting (photos *of* cameras)
CAMERA_COLLECTOR_GROUPS = [
    "52241291750@N01",  # Vintage Cameras
    "79963590@N00",     # Classic Camera Collection
    "14808925@N25",     # Old Cameras
]

LICENSE_NAMES = {
    "1": "CC-BY-NC-SA-2.0", "2": "CC-BY-NC-2.0", "3": "CC-BY-NC-ND-2.0",
    "4": "CC-BY-2.0", "5": "CC-BY-SA-2.0", "6": "CC-BY-ND-2.0",
    "9": "CC0-1.0", "10": "PDM-1.0",
}


def _photo_url(photo: dict, size: str = "b") -> str:
    """Construct a Flickr static image URL from photo info.

    Size suffixes: s=75x75, q=150x150, t=100, m=240, n=320, z=640, c=800, b=1024, h=1600
    """
    return (
        f"https://live.staticflickr.com/{photo['server']}"
        f"/{photo['id']}_{photo['secret']}_{size}.jpg"
    )


async def search_flickr_images(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
) -> list[dict] | None:
    """Search Flickr for CC-licensed images of a camera.

    Returns list of {"url", "source", "license", "caption"} or None.
    """
    api_key = os.environ.get("FLICKR_API_KEY")
    if not api_key:
        return None

    query = f"{manufacturer} {camera_name} camera" if manufacturer else f"{camera_name} camera"
    params = {
        "method": "flickr.photos.search",
        "api_key": api_key,
        "text": query,
        "license": CC_LICENSES,
        "media": "photos",
        "content_type": "1",  # photos only
        "sort": "relevance",
        "per_page": "5",
        "format": "json",
        "nojsoncallback": "1",
        "extras": "license,owner_name",
    }

    try:
        resp = await client.get(FLICKR_API, params=params)
        data = resp.json()
        photos = data.get("photos", {}).get("photo", [])
        if not photos:
            return None

        results = []
        for photo in photos[:3]:
            license_id = str(photo.get("license", ""))
            results.append({
                "url": _photo_url(photo, "b"),
                "source": "flickr_search",
                "license": LICENSE_NAMES.get(license_id, f"flickr-license-{license_id}"),
                "caption": f"Photo by {photo.get('ownername', 'unknown')} on Flickr",
            })
        return results if results else None
    except Exception:
        return None
