"""Collect Chinese camera data from chinesecamera.com (国产相机档案).

This site is a dedicated Chinese camera archive with structured data:
brand, model, factory, year, film format, lens mount, shutter, etc.
~252 unique camera entries with images.
"""

from __future__ import annotations

import asyncio
import re
import ssl
from html.parser import HTMLParser
from urllib.parse import quote, unquote

from src.models.camera import Camera, ImageReference, SourceReference
from src.normalization.manufacturers import get_manufacturer_country, normalize_manufacturer
from src.utils.data_io import save_records
from src.utils.http import RateLimitedClient

import httpx

BASE_URL = "http://www.chinesecamera.com"

# Map Chinese camera type names to our canonical types
_TYPE_MAP = {
    "单反": "SLR",
    "双反": "TLR",
    "旁轴": "Rangefinder",
    "折叠": "Folding",
    "简易": "Box camera",
    "座机": "View camera",
    "外拍机": "View camera",
    "转机": "Panoramic",
    "全景": "Panoramic",
    "微型": "Subminiature",
}

# Map Chinese film format names
_FORMAT_MAP = {
    "35mm": "135",
    "135": "135",
    "120": "120",
    "127": "127",
    "110": "110",
    "4x5": "4x5",
}

# Skip these "cameras" (not consumer cameras)
_SKIP_PREFIXES = {
    "广告品",  # advertising cameras
    "特种",    # special/military
    "企鹅-监控",  # surveillance
    "蓝箭-950",   # scanning device
    "旋光",       # rotating optical device
    "科服卡",     # micro camera
}


class _ContentExtractor(HTMLParser):
    """Extract text from #content-area div."""

    def __init__(self):
        super().__init__()
        self.texts: list[str] = []
        self.in_content = False

    def handle_starttag(self, tag, attrs):
        for name, val in attrs:
            if name == "id" and val == "content-area":
                self.in_content = True
            if name == "id" and val in ("footer", "sidebar-left"):
                self.in_content = False

    def handle_data(self, data):
        if self.in_content:
            s = data.strip()
            if s:
                self.texts.append(s)


def _parse_camera_page(html_text: str, page_url: str) -> dict | None:
    """Parse a camera detail page into a structured dict."""
    parser = _ContentExtractor()
    parser.feed(html_text)
    texts = parser.texts

    if len(texts) < 4:
        return None

    # Parse the structured fields by their labels
    fields: dict[str, str] = {}
    field_labels = [
        "品牌型号", "生产厂商", "生产时间", "原始价格", "说明书",
        "胶卷规格", "卡口类型", "测光", "焦距(mm)", "光圈",
        "快门类型", "快门速度", "尺寸(mm)", "重量(g)", "简介",
    ]
    i = 0
    while i < len(texts):
        if texts[i] in field_labels and i + 1 < len(texts):
            key = texts[i]
            # Collect values until next label
            vals = []
            j = i + 1
            while j < len(texts) and texts[j] not in field_labels and texts[j] not in ("相关文献资料", "相关附件"):
                vals.append(texts[j])
                j += 1
            fields[key] = " ".join(vals).strip()
            i = j
        else:
            i += 1

    brand_model = fields.get("品牌型号", "").strip()
    if not brand_model:
        return None

    # Split brand and model
    parts = brand_model.split(None, 1)
    brand = parts[0] if parts else ""
    model = parts[1] if len(parts) > 1 else brand_model

    # Clean up the full name
    name = brand_model.replace(" -", " ").strip()
    # Remove leading dash from model
    if model.startswith("-"):
        model = model[1:].strip()
        name = f"{brand} {model}"

    # Parse year
    year_str = fields.get("生产时间", "").strip()
    year_intro = None
    year_disc = None
    if year_str and year_str != "--":
        m = re.search(r"(\d{4})\s*[-–]\s*(\d{4})", year_str)
        if m:
            year_intro = int(m.group(1))
            year_disc = int(m.group(2))
        else:
            m = re.search(r"(\d{4})", year_str)
            if m:
                year_intro = int(m.group(1))

    # Film format
    film_raw = fields.get("胶卷规格", "").strip()
    film_format = None
    if film_raw and film_raw != "--":
        for key, fmt in _FORMAT_MAP.items():
            if key in film_raw:
                film_format = fmt
                break
        if not film_format:
            film_format = film_raw

    # Camera type — look in the "简介" area for type keywords
    camera_type = None
    intro = fields.get("简介", "").strip()
    for cn_type, en_type in _TYPE_MAP.items():
        if cn_type in intro or cn_type in brand_model:
            camera_type = en_type
            break

    # Lens mount
    lens_mount = fields.get("卡口类型", "").strip()
    if lens_mount in ("--", ""):
        lens_mount = None

    # Weight
    weight_g = None
    weight_str = fields.get("重量(g)", "").strip()
    if weight_str and weight_str != "--":
        m = re.search(r"(\d+)", weight_str)
        if m:
            weight_g = int(m.group(1))

    # Dimensions
    dimensions = fields.get("尺寸(mm)", "").strip()
    if dimensions in ("--", ""):
        dimensions = None

    # Shutter
    shutter = fields.get("快门速度", "").strip()
    if shutter in ("--", ""):
        shutter = None

    # Extract image URLs
    images = []
    # Get icon/main image
    icon_match = re.search(
        r'src="(http://www\.chinesecamera\.com/system/files/imagecache/Camera_image_icon/[^"]+\.(?:jpg|jpeg|png))"',
        html_text,
    )
    if icon_match:
        images.append(icon_match.group(1))
    # Get gallery images (watermark versions = larger)
    for m in re.finditer(
        r'href="(http://www\.chinesecamera\.com/system/files/imagecache/watermark/camera/[^"]+\.(?:jpg|jpeg|png))"',
        html_text,
    ):
        if m.group(1) not in images:
            images.append(m.group(1))
    # Get list-size images
    for m in re.finditer(
        r'src="(http://www\.chinesecamera\.com/system/files/imagecache/Camera_image_list/[^"]+\.(?:jpg|jpeg|png))"',
        html_text,
    ):
        if m.group(1) not in images:
            images.append(m.group(1))
    # Fallback: any tmp images
    for m in re.finditer(
        r'src="(http://www\.chinesecamera\.com/system/files/imagecache/Camera_image_icon/[^"]+\.(?:jpg|jpeg|png))"',
        html_text,
    ):
        if m.group(1) not in images:
            images.append(m.group(1))

    # Original price (CNY)
    price_cny = None
    price_str = fields.get("原始价格", "").strip()
    if price_str and price_str != "--":
        m = re.search(r"(\d+(?:\.\d+)?)", price_str)
        if m:
            price_cny = float(m.group(1))

    return {
        "name": name,
        "brand": brand,
        "model": model,
        "factory": fields.get("生产厂商", ""),
        "year_introduced": year_intro,
        "year_discontinued": year_disc,
        "film_format": film_format,
        "camera_type": camera_type,
        "lens_mount": lens_mount,
        "weight_g": weight_g,
        "dimensions": dimensions,
        "shutter_speed_range": shutter,
        "images": images,
        "page_url": page_url,
        "price_cny": price_cny,
    }


def _make_ssl_client() -> httpx.AsyncClient:
    """Create an httpx client that skips SSL verification for chinesecamera.com."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    return httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=ssl_ctx)


async def _get_all_camera_urls() -> list[str]:
    """Scrape all camera page URLs from paginated listing + brand pages."""
    urls: set[str] = set()
    brand_ids: set[str] = set()

    async with _make_ssl_client() as client:
        # Phase 1: Paginated main list
        for page in range(30):
            url = f"{BASE_URL}/cameras?page={page}"
            try:
                resp = await client.get(url)
                links = re.findall(r'href="(/camera/[^"]+)"', resp.text)
                if not links and page > 5:
                    break
                urls.update(links)
                # Collect brand page IDs from first page
                if page == 0:
                    brand_ids.update(re.findall(r'href="/cameras/(\d+)"', resp.text))
                await asyncio.sleep(1.0)
            except Exception as e:
                print(f"  Failed to fetch page {page}: {e}")
                break

        print(f"  Paginated list: {len(urls)} cameras, {len(brand_ids)} brand pages")

        # Phase 2: Crawl each brand page (may have cameras not in paginated list)
        for bid in sorted(brand_ids, key=int):
            brand_url = f"{BASE_URL}/cameras/{bid}"
            try:
                resp = await client.get(brand_url)
                links = re.findall(r'href="(/camera/[^"]+)"', resp.text)
                urls.update(links)
                # Check sub-pages within brand
                sub_pages = re.findall(rf'href="(/cameras/{bid}\?page=\d+)"', resp.text)
                for sp in sub_pages:
                    resp2 = await client.get(f"{BASE_URL}{sp}")
                    urls.update(re.findall(r'href="(/camera/[^"]+)"', resp2.text))
                    await asyncio.sleep(0.5)
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"  Failed to fetch brand {bid}: {e}")

    return sorted(urls)


async def _fetch_camera_page(client: httpx.AsyncClient, path: str) -> str | None:
    """Fetch a single camera detail page."""
    url = f"{BASE_URL}{path}"
    try:
        resp = await client.get(url)
        return resp.text
    except Exception as e:
        print(f"  Failed to fetch {url}: {e}")
        return None


async def _collect() -> None:
    """Run the chinesecamera.com collection pipeline."""
    print("=" * 60)
    print("COLLECTING CAMERAS FROM CHINESECAMERA.COM (国产相机档案)")
    print("=" * 60)

    # Step 1: Get all camera page URLs
    print("\nEnumerating camera pages...")
    camera_paths = await _get_all_camera_urls()
    print(f"  Found {len(camera_paths)} camera pages")

    # Step 2: Filter out non-consumer cameras
    filtered_paths = []
    for path in camera_paths:
        decoded = unquote(path)
        skip = False
        for prefix in _SKIP_PREFIXES:
            if prefix in decoded:
                skip = True
                break
        if not skip:
            filtered_paths.append(path)

    print(f"  After filtering: {len(filtered_paths)} cameras")

    # Step 3: Fetch and parse each camera page
    cameras: list[Camera] = []
    now_iso = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()

    async with _make_ssl_client() as client:
        for idx, path in enumerate(filtered_paths):
            if (idx + 1) % 20 == 0:
                print(f"  Processing {idx + 1}/{len(filtered_paths)}...")

            html = await _fetch_camera_page(client, path)
            if not html:
                continue

            await asyncio.sleep(2.0)  # Rate limit

            page_url = f"{BASE_URL}{path}"
            parsed = _parse_camera_page(html, page_url)
            if not parsed:
                continue

            brand = parsed["brand"]
            manufacturer_norm = normalize_manufacturer(brand)
            manufacturer_country = get_manufacturer_country(brand) or "China"

            image_refs = []
            for img_url in parsed["images"]:
                image_refs.append(
                    ImageReference(
                        url=img_url,
                        source="chinesecamera",
                        caption=parsed["name"],
                    )
                )

            # Convert CNY price to USD if available
            price_launch_usd = None
            if parsed.get("price_cny") and parsed.get("year_introduced"):
                try:
                    from src.pricing.inflation import convert_to_usd
                    price_launch_usd = convert_to_usd(
                        parsed["price_cny"], "CNY", parsed["year_introduced"]
                    )
                except Exception:
                    pass  # pricing module may not be available yet

            camera = Camera(
                name=parsed["name"],
                manufacturer=brand,
                manufacturer_normalized=manufacturer_norm,
                manufacturer_country=manufacturer_country,
                camera_type=parsed["camera_type"],
                film_format=parsed["film_format"],
                year_introduced=parsed["year_introduced"],
                year_discontinued=parsed["year_discontinued"],
                lens_mount=parsed["lens_mount"],
                weight_g=parsed["weight_g"],
                dimensions=parsed["dimensions"],
                shutter_speed_range=parsed["shutter_speed_range"],
                price_launch_usd=price_launch_usd,
                images=image_refs,
                sources=[
                    SourceReference(
                        source="chinesecamera",
                        source_url=page_url,
                        retrieved_at=now_iso,
                    )
                ],
            )
            cameras.append(camera)
            print(f"    + {camera.name} ({camera.manufacturer}, {camera.film_format or '?'}, {camera.camera_type or '?'})")

    print(f"\nTotal cameras collected: {len(cameras)}")
    save_records(cameras, source="chinesecamera", entity_type="cameras")
    print("\nchinesecamera.com collection complete.")


def main() -> None:
    """Entry point for the chinesecamera.com collector."""
    asyncio.run(_collect())


if __name__ == "__main__":
    main()
