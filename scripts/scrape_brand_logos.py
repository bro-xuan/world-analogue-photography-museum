#!/usr/bin/env python3
"""Scrape brand logos from Google Images using Scrapling.

Usage:
    uv run python scripts/scrape_brand_logos.py [--force] [--limit N] [--brand NAME]

For each brand missing a logo, searches Google Images for "{brand} logo"
and downloads the best matching logo image.
"""

import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from scrapling import StealthyFetcher

LOGOS_DIR = Path("web/public/logos")
BRANDS_JSON = Path("web/public/data/brands.json")

# Brands to skip (truly generic names, not actual camera brands)
SKIP_BRANDS: set[str] = {
    "Le", "Mini", "Nova", "Sport", "Capital", "Boots", "Revue",
    "YC-75X100", "PENTAREX", "PERICA",
}

# Custom search queries for ambiguous brand names
SEARCH_OVERRIDES: dict[str, str] = {
    "Argus": "Argus camera company logo",
    "Alpa": "Alpa camera Switzerland logo",
    "FED": "FED camera Soviet logo",
    "Kiev": "Kiev Arsenal camera logo",
    "Miranda": "Miranda Camera Company logo",
    "Seagull": "Seagull camera Shanghai logo",
    "Riken": "Riken camera Ricoh logo",
    "Goerz": "C.P. Goerz camera logo",
    "ICA": "ICA camera company Dresden logo",
    "Coronet": "Coronet Camera Company logo",
    "Graflex": "Graflex camera logo",
    "Keystone": "Keystone camera company logo",
    "Concord": "Concord camera company logo",
    "Petri": "Petri camera Japan logo",
    "Revere": "Revere camera company logo",
    "Balda": "Balda camera Germany logo",
    "Wirgin": "Wirgin Edixa camera logo",
    "Robot": "Otto Berning Robot camera logo",
    "Berning Robot": "Otto Berning Robot camera logo",
    "Houghton": "Houghton Ensign camera logo",
    "Ernemann": "Ernemann camera Dresden logo",
    "Exakta": "Exakta Ihagee camera logo",
    "Ansco": "Ansco camera company logo",
    "Praktica": "Praktica camera logo",
    "Lomography": "Lomography logo",
    "Chinon": "Chinon camera logo",
    # Re-source wrong logos with Chinese terms
    "Phenix": "凤凰相机 凤凰光学 logo",
    "Pearl River": "珠江相机 广州照相机厂 logo",
    "Fengguang": "风光相机 logo",
    "Beijing": "北京照相机厂 logo",
    "Changchun": "长春照相机 长春光学 logo",
    "Xing Fu": "幸福相机 天津照相机厂 logo",
    # Missing logos — Chinese brands
    "Halina": "Halina camera Haking logo",
    "Haking": "Haking camera Hong Kong logo",
    "Huaxia": "华夏相机 logo",
    "Mudan": "牡丹相机 丹东照相机厂 logo",
    "Shanghai": "上海相机 上海照相机 logo",
    "Dongfang": "东方相机 天津照相机厂 logo",
    "Great Wall": "长城相机 logo",
    "Hongmei": "红梅相机 常州照相机厂 logo",
    "Hua Zhong": "华中相机 logo",
    "Youyi": "友谊相机 无锡照相机 logo",
    "Kongque": "孔雀相机 logo",
    "Qingdao": "青岛相机 logo",
    "Huashan": "华山相机 logo",
    "Huqiu": "虎丘相机 logo",
    # Missing logos — non-Chinese
    "Zorki": "Zorki camera KMZ Soviet logo",
    "Centon": "Centon camera UK logo",
    "Eastar": "Eastar camera brand logo",
    "Suntone": "Suntone camera brand logo",
    # Missing logos — obscure Chinese
    "Wanling": "万灵相机 logo",
    "Sanyou": "三友相机 logo",
    "Huaxi": "华西相机 logo",
    "Tianee": "天鹅相机 logo",
    "Taihu": "太湖相机 logo",
    "Mingjiia": "明佳相机 logo",
    "Baihua": "百花相机 logo",
    "Xihu": "西湖相机 logo",
    "Jindu": "金都相机 logo",
}

# Domains to avoid (watermarked, low quality, or non-logo results)
BAD_DOMAINS = {
    "alamy.com", "shutterstock.com", "dreamstime.com", "istockphoto.com",
    "gettyimages.com", "123rf.com", "adobe.com", "depositphotos.com",
    "alicdn.com", "aliexpress.com", "ebay.com", "amazon.com",
}


def _score_url(url: str, brand_name: str) -> int:
    """Score a URL for how likely it is a clean brand logo."""
    score = 0
    url_lower = url.lower()
    brand_lower = brand_name.lower().replace(" ", "")

    # Must contain brand name somewhere
    url_brand = url_lower.replace("-", "").replace("_", "").replace("%20", "")
    if brand_lower not in url_brand:
        score -= 50

    # Prefer logo-specific sources
    if "logo" in url_lower:
        score += 20
    if "brand" in url_lower:
        score += 10
    if "transparent" in url_lower:
        score += 15

    # Prefer vector/PNG with transparency
    if url_lower.endswith(".svg"):
        score += 25
    elif url_lower.endswith(".png"):
        score += 15
    elif url_lower.endswith(".webp"):
        score += 5
    elif url_lower.endswith(".jpg") or url_lower.endswith(".jpeg"):
        score -= 5

    # Prefer known logo sites
    logo_sites = [
        "1000logos.net", "brandslogos.com", "freebiesupply.com",
        "worldvectorlogo.com", "pngimg.com", "seeklogo.com",
        "logowik.com", "logodownload.org", "commons.wikimedia.org",
        "upload.wikimedia.org", "pngegg.com", "logopng.com",
    ]
    for site in logo_sites:
        if site in url_lower:
            score += 15
            break

    # Penalize bad domains
    for domain in BAD_DOMAINS:
        if domain in url_lower:
            score -= 100
            break

    # Camera-specific domain bonuses
    camera_sites = ["camera-wiki.org", "camerapedia.org", "chinesecamera.com", "collectiblend.com"]
    for site in camera_sites:
        if site in url_lower:
            score += 10
            break

    # False-positive penalties (brands with same names in other industries)
    false_positive_terms = ["bubble tea", "railway", "crrc", "real estate", "tang", "collection", "eyewear", "glasses", "optical frame"]
    for term in false_positive_terms:
        if term.replace(" ", "") in url_lower.replace("-", "").replace("_", ""):
            score -= 40
            break

    # Penalize photo-like URLs
    if any(w in url_lower for w in ["photo", "camera-", "store", "shop", "product"]):
        score -= 20

    # Penalize tiny thumbnails
    if "thumb" in url_lower or "small" in url_lower:
        score -= 10

    # Bonus for "black-and-white" (our display style is brightness-0 anyway)
    if "black" in url_lower and "white" in url_lower:
        score += 5

    return score


def _extract_image_urls(html: str) -> list[str]:
    """Extract real image URLs from Google Images HTML."""
    # Find all image URLs (not base64, not google internal)
    urls = re.findall(r'https?://[^"\'\\<>\s]+\.(?:png|jpg|jpeg|svg|webp)', html)
    unique = []
    seen = set()
    for u in urls:
        # Clean URL (remove trailing params artifacts)
        u = u.split("\\")[0].split("&amp;")[0]
        if u not in seen and "google" not in u and "gstatic" not in u:
            seen.add(u)
            unique.append(u)
    return unique


def _download_image(url: str, dest: Path, max_size: int = 150_000) -> bool:
    """Download an image via curl and verify it's a valid logo (not a photo)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "15",
             "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
             "-o", str(dest), url],
            capture_output=True, timeout=20,
        )
        if result.returncode != 0 or not dest.exists():
            return False

        size = dest.stat().st_size
        if size < 500:
            dest.unlink()
            return False

        # Logos should be small — photos are usually >500KB
        if size > max_size:
            dest.unlink()
            return False

        # Verify it's an image
        ft = subprocess.run(
            ["file", "-b", str(dest)], capture_output=True, text=True
        ).stdout.strip()
        if "HTML" in ft or "ASCII" in ft or "text" in ft.lower():
            dest.unlink()
            return False

        return True
    except Exception:
        if dest.exists():
            dest.unlink()
        return False


def scrape_logo(fetcher: StealthyFetcher, brand_name: str, dest: Path) -> bool:
    """Search Google Images and download the best logo for a brand."""
    query = SEARCH_OVERRIDES.get(brand_name, f"{brand_name} camera brand logo")
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&tbm=isch"

    try:
        page = fetcher.fetch(url)
    except Exception as e:
        print(f"    fetch error: {e}")
        return False

    if page.status != 200:
        print(f"    HTTP {page.status}")
        return False

    html = page.html_content
    image_urls = _extract_image_urls(html)

    if not image_urls:
        return False

    # Score and sort URLs
    scored = [(u, _score_url(u, brand_name)) for u in image_urls]
    scored.sort(key=lambda x: -x[1])

    # Try top 5 candidates
    for url, score in scored[:5]:
        if score < -20:
            continue
        ext = ".png"
        if url.lower().endswith(".svg"):
            ext = ".svg"
        elif url.lower().endswith(".webp"):
            ext = ".webp"

        # Always save as .png name (our system expects .png)
        if _download_image(url, dest):
            print(f"    downloaded from: {url[:80]}... (score={score})")
            return True

    return False


def main():
    force = "--force" in sys.argv
    limit = None
    brand_filter = None

    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
        if arg == "--brand" and i + 1 < len(sys.argv):
            brand_filter = sys.argv[i + 1]

    if not BRANDS_JSON.exists():
        print(f"ERROR: {BRANDS_JSON} not found.")
        sys.exit(1)

    brands_data = json.loads(BRANDS_JSON.read_text())
    all_brands = brands_data["allBrands"]
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)

    # Filter to brands needing logos
    to_process = []
    for brand in all_brands:
        slug = brand["slug"]
        name = brand["name"]
        dest = LOGOS_DIR / f"{slug}.png"

        if brand_filter and name != brand_filter:
            continue
        if dest.exists() and not force:
            continue
        if name in SKIP_BRANDS:
            continue
        to_process.append(brand)

    if limit:
        to_process = to_process[:limit]

    print(f"Processing {len(to_process)} brands (of {len(all_brands)} total)")
    print(f"Already have {len(all_brands) - len(to_process)} logos\n")

    fetcher = StealthyFetcher()
    found = 0
    failed = []

    for i, brand in enumerate(to_process):
        slug = brand["slug"]
        name = brand["name"]
        dest = LOGOS_DIR / f"{slug}.png"
        count = brand["cameraCount"]

        print(f"[{i+1}/{len(to_process)}] {name} ({count} cameras)")

        if scrape_logo(fetcher, name, dest):
            size = dest.stat().st_size
            print(f"  ✓ saved {slug}.png ({size:,}b)")
            found += 1
        else:
            print(f"  ✗ no logo found")
            failed.append(name)

        # Rate limit: wait between searches
        time.sleep(2)

    print(f"\n{'='*50}")
    print(f"Results: {found}/{len(to_process)} new logos downloaded")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
