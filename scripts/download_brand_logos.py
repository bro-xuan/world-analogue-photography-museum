#!/usr/bin/env python3
"""Download brand logos from Wikimedia Commons.

Usage:
    uv run python scripts/download_brand_logos.py [--force]

Logos are saved to web/public/logos/{slug}.png
"""

import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

LOGOS_DIR = Path("web/public/logos")
BRANDS_JSON = Path("web/public/data/brands.json")

# Curated mapping: brand name → exact Wikimedia Commons filename
# These are verified logo files on Commons.
CURATED_LOGOS: dict[str, str] = {
    # Major global brands
    "Kodak": "Eastman Kodak Company logo (2016)(no background).svg",
    "Leica": "Leica Camera logo.svg",
    "Canon": "Canon wordmark.svg",
    "Nikon": "Nikon Logo.svg",
    "Fujifilm": "Fujifilm logo.svg",
    "Olympus": "Olympus Corporation logo.svg",
    "Pentax": "Pentax Logo.svg",
    "Ricoh": "Ricoh logo.svg",
    "Hasselblad": "Hasselblad logo.svg",
    "Polaroid": "Polaroid Logo.svg",
    "Mamiya": "Mamiya logo.svg",
    "Yashica": "YASHICA LOGO.svg",
    "Rollei": "Rollei logo.svg",
    "Minolta": "Minolta logo (1981-2003).svg",
    "Konica": "Logo Konica Minolta.svg",
    "Contax": "Contax Logo.svg",
    "Praktica": "Praktica logo.svg",
    # German brands
    "Zeiss": "Zeiss logo.svg",
    "Voigtlander": "Voigtlaender logo blau.jpg",
    "Agfa": "Agfa logo.svg",
    "Braun": "Braun Logo.svg",
    "Minox": "Minox logo.svg",
    # US brands
    "Bell & Howell": "Bell & Howell logo.svg",
    "Vivitar": "Vivitar logo.svg",
    # Other notable brands
    "Hanimex": "Hanimex logo.svg",
    "Ducati": "Ducati red logo.svg",
}

# Custom search terms for brands not in CURATED_LOGOS
SEARCH_OVERRIDES: dict[str, str] = {
    "Ernemann": "Ernemann camera",
    "Exakta": "Ihagee Exakta",
    "Houghton": "Houghton Ensign camera",
    "ICA": "ICA camera company",
    "Ansco": "Ansco Agfa camera",
    "Wirgin": "Wirgin camera Edixa",
    "Alpa": "Alpa camera Swiss",
    "Petri": "Petri camera Japan",
    "Coronet": "Coronet Camera Company",
    "FED": "FED camera Soviet",
    "Kiev": "Kiev Arsenal camera",
    "Minox": "Minox subminiature camera",
    "Miranda": "Miranda Camera Company",
    "Seagull": "Shanghai Seagull camera",
    "Keystone": "Keystone camera company",
    "Adox": "Adox camera film",
    "Soligor": "Soligor camera lens",
    "Concord": "Concord camera company",
    "Edixa": "Wirgin Edixa camera",
    "Instax": "Fujifilm Instax",
    "Riken": "Riken camera Ricoh",
    "Balda": "Balda camera Germany",
    "Goerz": "C.P. Goerz optical",
    # Re-source wrong logos with Chinese terms
    "Berning Robot": "Otto Berning Robot camera",
    "Phenix": "凤凰相机 凤凰光学",
    "Pearl River": "珠江相机 广州照相机厂",
    "Fengguang": "风光相机",
    "Beijing": "北京照相机厂",
    "Changchun": "长春照相机 长春光学",
    "Xing Fu": "幸福相机 天津照相机厂",
    # Missing logos — Chinese brands
    "Halina": "Halina camera Haking",
    "Haking": "Haking camera Hong Kong",
    "Huaxia": "华夏相机",
    "Mudan": "牡丹相机 丹东照相机厂",
    "Shanghai": "上海相机 上海照相机",
    "Dongfang": "东方相机 天津照相机厂",
    "Great Wall": "长城相机",
    "Hongmei": "红梅相机 常州照相机厂",
    "Hua Zhong": "华中相机",
    "Youyi": "友谊相机 无锡照相机",
    "Kongque": "孔雀相机",
    "Qingdao": "青岛相机",
    "Huashan": "华山相机",
    "Huqiu": "虎丘相机",
    # Missing logos — non-Chinese
    "Zorki": "Zorki camera KMZ Soviet",
    "Centon": "Centon camera UK",
    "Eastar": "Eastar camera brand",
    "Suntone": "Suntone camera brand",
    # Missing logos — obscure Chinese
    "Wanling": "万灵相机",
    "Sanyou": "三友相机",
    "Huaxi": "华西相机",
    "Tianee": "天鹅相机",
    "Taihu": "太湖相机",
    "Mingjiia": "明佳相机",
    "Baihua": "百花相机",
    "Xihu": "西湖相机",
    "Jindu": "金都相机",
}

# Brands to skip (truly generic names, not actual camera brands)
SKIP_BRANDS: set[str] = {
    "Le", "Mini", "Nova", "Sport", "Capital", "Boots", "Revue",
    "YC-75X100", "PENTAREX", "PERICA",
}


def _curl_json(url: str) -> dict | None:
    """GET request via curl, return parsed JSON."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "30", url],
            capture_output=True, text=True, timeout=35,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        pass
    return None


def _curl_download(url: str, dest: Path) -> bool:
    """Download file via curl."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "30", "-o", str(dest), url],
            capture_output=True, timeout=35,
        )
        if result.returncode == 0 and dest.exists() and dest.stat().st_size > 500:
            # Verify it's actually an image, not HTML
            ft = subprocess.run(
                ["file", "-b", str(dest)], capture_output=True, text=True
            ).stdout.strip()
            if "HTML" in ft or "ASCII" in ft:
                dest.unlink()
                return False
            return True
        if dest.exists():
            dest.unlink()
    except Exception:
        if dest.exists():
            dest.unlink()
    return False


def commons_imageinfo_url(filename: str, width: int = 400) -> str | None:
    """Use the Commons imageinfo API to get a proper thumbnail URL."""
    title = f"File:{filename.replace(' ', '_')}"
    api_url = (
        f"https://commons.wikimedia.org/w/api.php?"
        f"action=query&titles={urllib.parse.quote(title)}"
        f"&prop=imageinfo&iiprop=url&iiurlwidth={width}&format=json"
    )
    data = _curl_json(api_url)
    if not data:
        return None

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        if page.get("missing") is not None:
            continue
        ii = page.get("imageinfo", [{}])
        if ii:
            return ii[0].get("thumburl") or ii[0].get("url")
    return None


def search_commons_logo(search_term: str) -> str | None:
    """Search Wikimedia Commons for a logo, return thumbnail URL.

    Prefers SVG files (clean vector logos) over photographs.
    """
    encoded = urllib.parse.quote(search_term + " logo")
    api_url = (
        f"https://commons.wikimedia.org/w/api.php?"
        f"action=query&generator=search"
        f"&gsrsearch={encoded}&gsrnamespace=6&gsrlimit=5"
        f"&prop=imageinfo&iiprop=url|mime&iiurlwidth=400&format=json"
    )
    data = _curl_json(api_url)
    if not data:
        return None

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None

    # Score results: prefer SVG (vector logos) and files with "logo" in name
    candidates = []
    for page in pages.values():
        title = page.get("title", "")
        ii = page.get("imageinfo", [{}])
        if not ii:
            continue
        info = ii[0]
        mime = info.get("mime", "")
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue

        score = 0
        title_lower = title.lower()
        if "logo" in title_lower:
            score += 10
        if mime == "image/svg+xml" or title_lower.endswith(".svg"):
            score += 5
        # Penalize photos
        if any(w in title_lower for w in ["photo", "camera", "building", "tower", "headquarter"]):
            score -= 10
        # Penalize non-image results
        if "pdf" in mime or "video" in mime:
            score -= 20

        candidates.append((score, url))

    candidates.sort(key=lambda x: -x[0])
    if candidates and candidates[0][0] >= 0:
        return candidates[0][1]
    return None


def download_curated_logo(filename: str, dest: Path) -> bool:
    """Download a logo by its exact Commons filename."""
    url = commons_imageinfo_url(filename, 400)
    if url:
        return _curl_download(url, dest)
    return False


def main():
    force = "--force" in sys.argv

    if not BRANDS_JSON.exists():
        print(f"ERROR: {BRANDS_JSON} not found.")
        sys.exit(1)

    brands_data = json.loads(BRANDS_JSON.read_text())
    all_brands = brands_data["allBrands"]
    print(f"Processing {len(all_brands)} brands...\n")

    LOGOS_DIR.mkdir(parents=True, exist_ok=True)

    found = 0
    missing = []

    for brand in all_brands:
        slug = brand["slug"]
        name = brand["name"]
        dest = LOGOS_DIR / f"{slug}.png"

        if dest.exists() and not force:
            size = dest.stat().st_size
            print(f"  ✓ {name} — exists ({size:,}b)")
            found += 1
            continue

        if name in SKIP_BRANDS:
            print(f"  — {name} — skipped")
            missing.append(name)
            continue

        # Strategy 1: Curated filename
        if name in CURATED_LOGOS:
            if download_curated_logo(CURATED_LOGOS[name], dest):
                size = dest.stat().st_size
                print(f"  ✓ {name} — curated ({size:,}b)")
                found += 1
                time.sleep(0.3)
                continue
            else:
                print(f"    (curated logo failed, trying search)")

        time.sleep(0.3)

        # Strategy 2: Commons search
        search_term = SEARCH_OVERRIDES.get(name, name)
        url = search_commons_logo(search_term)
        if url:
            if _curl_download(url, dest):
                size = dest.stat().st_size
                print(f"  ✓ {name} — Commons search ({size:,}b)")
                found += 1
                time.sleep(0.3)
                continue

        print(f"  ✗ {name} — no logo found")
        missing.append(name)
        time.sleep(0.3)

    print(f"\n{'='*50}")
    print(f"Results: {found}/{len(all_brands)} found, {len(missing)} missing")
    if missing:
        print(f"\nMissing logos ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")


if __name__ == "__main__":
    main()
