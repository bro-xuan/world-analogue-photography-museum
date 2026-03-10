"""Search DuckDuckGo Images and eBay for camera product photos.

DuckDuckGo: Uses the DDG image search API (no key needed).
eBay: Scrapes eBay completed listings for product photos (no key needed).
"""

from __future__ import annotations

import re

from src.utils.http import RateLimitedClient


async def search_duckduckgo_images(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
    max_results: int = 1,
) -> list[dict] | None:
    """Search DuckDuckGo Images for camera product photos.

    Uses the DDG vqd token flow:
    1. GET https://duckduckgo.com/ with query to get vqd token
    2. GET https://duckduckgo.com/i.js with vqd token to get image results

    Returns list of {"url", "source", "license", "caption"} or None.
    """
    query = f"{manufacturer} {camera_name} camera" if manufacturer else f"{camera_name} camera"

    try:
        # Step 1: Get vqd token
        resp = await client.get(
            "https://duckduckgo.com/",
            params={"q": query},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        )
        # Extract vqd token from response
        vqd_match = re.search(r'vqd=["\']([^"\']+)', resp.text)
        if not vqd_match:
            # Try alternative pattern
            vqd_match = re.search(r'vqd=([\d-]+)', resp.text)
        if not vqd_match:
            return None
        vqd = vqd_match.group(1)

        # Step 2: Fetch image results
        resp = await client.get(
            "https://duckduckgo.com/i.js",
            params={
                "l": "us-en",
                "o": "json",
                "q": query,
                "vqd": vqd,
                "f": ",,,,,",
                "p": "1",
            },
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://duckduckgo.com/",
            },
        )
        data = resp.json()
        results_list = data.get("results", [])
        if not results_list:
            return None

        results = []
        for item in results_list[:max_results * 3]:  # Check more than needed to filter
            image_url = item.get("image", "")
            title = item.get("title", "")
            source_url = item.get("url", "")

            if not image_url:
                continue

            # Skip non-image URLs
            if not any(ext in image_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                continue

            # Skip known bad sources
            if any(bad in image_url.lower() for bad in ['logo', 'icon', 'banner', 'avatar']):
                continue

            results.append({
                "url": image_url,
                "source": "duckduckgo",
                "license": "unknown",
                "caption": f"DuckDuckGo: {title}" if title else "DuckDuckGo image search",
            })

            if len(results) >= max_results:
                break

        return results if results else None
    except Exception as e:
        print(f"  DDG search failed for {query}: {e}", flush=True)
        return None


async def search_ebay_images(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
    max_results: int = 1,
) -> list[dict] | None:
    """Search eBay for camera product photos.

    Scrapes eBay search results page for product listing images.
    These tend to be clean product photos taken by sellers.

    Returns list of {"url", "source", "license", "caption"} or None.
    """
    query = f"{manufacturer} {camera_name} film camera" if manufacturer else f"{camera_name} film camera"

    try:
        resp = await client.get(
            "https://www.ebay.com/sch/i.html",
            params={
                "_nkw": query,
                "_sacat": "15230",  # Film Cameras category
                "_ipg": "25",
            },
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
        )

        if resp.status_code != 200:
            return None

        html = resp.text

        # Extract image URLs from eBay listing results
        # eBay uses i.ebayimg.com for listing images
        # Pattern: src="https://i.ebayimg.com/images/g/XXXXX/s-l225.jpg"
        # We want the larger version: s-l500.jpg or s-l1600.jpg
        img_pattern = re.compile(
            r'src=["\']?(https://i\.ebayimg\.com/images/g/[^"\'>\s]+)["\']?'
        )
        matches = img_pattern.findall(html)

        if not matches:
            # Try thumbs pattern
            img_pattern = re.compile(
                r'src=["\']?(https://i\.ebayimg\.com/thumbs/images/g/[^"\'>\s]+)["\']?'
            )
            matches = img_pattern.findall(html)

        if not matches:
            return None

        results = []
        seen_urls = set()
        for url in matches:
            # Upgrade to larger image size
            large_url = re.sub(r's-l\d+', 's-l500', url)

            # Deduplicate
            base_id = re.search(r'/g/([^/]+)/', large_url)
            if base_id:
                uid = base_id.group(1)
                if uid in seen_urls:
                    continue
                seen_urls.add(uid)

            results.append({
                "url": large_url,
                "source": "ebay",
                "license": "fair-use",
                "caption": "eBay listing photo",
            })

            if len(results) >= max_results:
                break

        return results if results else None
    except Exception as e:
        print(f"  eBay search failed for {query}: {e}", flush=True)
        return None


async def search_web_images(
    camera_name: str,
    manufacturer: str,
    client: RateLimitedClient,
    max_results: int = 8,
) -> list[dict] | None:
    """Search DuckDuckGo and eBay for camera images. Combines results from both."""
    results = []
    seen_urls = set()

    # Try DuckDuckGo first
    ddg = await search_duckduckgo_images(camera_name, manufacturer, client, max_results)
    if ddg:
        for r in ddg:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                results.append(r)

    # Also try eBay for additional photos
    if len(results) < max_results:
        remaining = max_results - len(results)
        ebay = await search_ebay_images(camera_name, manufacturer, client, remaining)
        if ebay:
            for r in ebay:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    results.append(r)

    return results if results else None
