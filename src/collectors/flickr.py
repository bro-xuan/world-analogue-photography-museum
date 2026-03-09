"""Collect camera data by scraping flickr.com/cameras/ with Scrapling."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone

from scrapling import StealthyFetcher

from src.models.camera import Camera, SourceReference
from src.normalization.manufacturers import normalize_manufacturer
from src.patterns.digital import is_digital_name
from src.utils.data_io import save_records

BASE_URL = "https://www.flickr.com/cameras/"

# --------------------------------------------------------------------------- #
# Filtering heuristics
# --------------------------------------------------------------------------- #


KNOWN_ANALOGUE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bAE-1\b", re.I),
    re.compile(r"\bA-1\b", re.I),
    re.compile(r"\bF-1\b", re.I),
    re.compile(r"\bEOS\s*(?:1[NV]?|3|5|10[0S]?|50[0E]?|500N|620|630|650|700|750|850|1000|3000|5000)\b", re.I),
    re.compile(r"\bK1000\b", re.I),
    re.compile(r"\bK\d{3,4}\b"),  # Pentax K-mount film bodies like K200, K1000
    re.compile(r"\bME\s*Super\b", re.I),
    re.compile(r"\bMX\b"),
    re.compile(r"\bLX\b"),
    re.compile(r"\bSPOTMATIC\b", re.I),
    re.compile(r"\bF[2-6]\b"),  # Nikon F2, F3, F4, F5, F6
    re.compile(r"\bFM\d?\b"),  # Nikon FM, FM2, FM3
    re.compile(r"\bFE\d?\b"),  # Nikon FE, FE2
    re.compile(r"\bF[MAE]\d?\b"),  # Nikon FA, FE, FM
    re.compile(r"\bNikkormat\b", re.I),
    re.compile(r"\bNikonos\b", re.I),
    re.compile(r"\bN\d{2,4}\b"),  # Nikon N80, N8008, etc.
    re.compile(r"\bOM-[1234]\b"),  # Olympus OM series film
    re.compile(r"\bTrip\s*35\b", re.I),
    re.compile(r"\bXA\d?\b"),  # Olympus XA series
    re.compile(r"\bM[346]\b"),  # Leica M3, M4, M6
    re.compile(r"\bM[67](?:TTL)?\b", re.I),  # Leica M6, M7
    re.compile(r"\bMP\b"),  # Leica MP
    re.compile(r"\bCL\b"),  # Leica CL (film)
    re.compile(r"\bIIIf?\b"),  # Leica III
    re.compile(r"\bSRT\b", re.I),  # Minolta SRT
    re.compile(r"\bX-700\b", re.I),
    re.compile(r"\bX-570\b", re.I),
    re.compile(r"\bXD[-\s]?11\b", re.I),
    re.compile(r"\bXG[-\s]?\d\b", re.I),
    re.compile(r"\bHi-Matic\b", re.I),
    re.compile(r"\bRolleiflex\b", re.I),
    re.compile(r"\bRolleicord\b", re.I),
    re.compile(r"\bYashica-Mat\b", re.I),
    re.compile(r"\bElectro\s*35\b", re.I),
    re.compile(r"\bHasselblad\s*500\b", re.I),
    re.compile(r"\b500C/?M?\b"),  # Hasselblad 500C, 500CM
    re.compile(r"\bMamiya\s*(?:RB|RZ|645|C330|C220|7|6)\b", re.I),
    re.compile(r"\bBronica\b", re.I),
    re.compile(r"\bHolga\b", re.I),
    re.compile(r"\bDiana\b", re.I),
    re.compile(r"\bLomo\s*LC-?A\b", re.I),
    re.compile(r"\bSprocket\s*Rocket\b", re.I),
    re.compile(r"\bPolaroid\b", re.I),
    re.compile(r"\bInstax\b", re.I),
    re.compile(r"\bSX-70\b", re.I),
    re.compile(r"\bSpectra\b", re.I),
    re.compile(r"\bSpeed\s*Graphic\b", re.I),
    re.compile(r"\bCrown\s*Graphic\b", re.I),
    re.compile(r"\bContax\s*(?:G[12]|T[23]?|RTS|S2|Aria|167)\b", re.I),
    re.compile(r"\bT[234]\b"),  # Contax T-series
    re.compile(r"\bElectra\b", re.I),
    re.compile(r"\bmju\b", re.I),  # Olympus mju / Stylus
    re.compile(r"\bStylus\b", re.I),
    re.compile(r"\bSure\s*Shot\b", re.I),
    re.compile(r"\bKlasse\b", re.I),
    re.compile(r"\bTiara\b", re.I),
    re.compile(r"\bNatura\b", re.I),
    re.compile(r"\bGA645\b", re.I),  # Fuji medium format film
    re.compile(r"\bGW690\b", re.I),
    re.compile(r"\bGS[Ww]?\d{3}\b"),  # Fuji rangefinder film
    # Chinese brands
    re.compile(r"\bSeagull\b", re.I),
    re.compile(r"\b海鸥\b"),
    re.compile(r"\bShanghai\b", re.I),
    # Soviet/Russian/Eastern European brands
    re.compile(r"\bZenit\b", re.I),
    re.compile(r"\bFED\b"),
    re.compile(r"\bZorki\b", re.I),
    re.compile(r"\bSmena\b", re.I),
    re.compile(r"\bPraktica\b", re.I),
]


def _is_analogue(model_name: str) -> bool:
    """Return True if the model name matches known analogue camera patterns."""
    for pat in KNOWN_ANALOGUE_PATTERNS:
        if pat.search(model_name):
            return True
    return False


def _classify(model_name: str) -> str:
    """Classify a camera model name: 'analogue', 'digital', or 'uncertain'."""
    if is_digital_name(model_name):
        return "digital"
    if _is_analogue(model_name):
        return "analogue"
    return "uncertain"


# --------------------------------------------------------------------------- #
# Scraping
# --------------------------------------------------------------------------- #

def _scrape_brands(fetcher: StealthyFetcher) -> list[dict[str, str]]:
    """Scrape the main cameras page to get brand names and URLs.

    Returns list of dicts with 'name' and 'slug' keys.
    """
    print("Fetching brands from flickr.com/cameras/ ...")
    page = fetcher.fetch(BASE_URL)
    if page.status != 200:
        print(f"Failed to fetch brands page: HTTP {page.status}")
        return []

    brands = []
    # Brand links are <a> elements pointing to /cameras/{brand}/
    for link in page.css("a[href]"):
        href = link.attrib.get("href", "")
        # Match /cameras/{brand}/ but not /cameras/ itself
        m = re.match(r"^/cameras/([^/]+)/?$", href)
        if not m:
            continue
        slug = m.group(1)
        name = link.text.strip() if link.text else slug
        if name and slug:
            brands.append({"name": name, "slug": slug})

    # Deduplicate by slug
    seen = set()
    unique = []
    for b in brands:
        if b["slug"] not in seen:
            seen.add(b["slug"])
            unique.append(b)

    print(f"Found {len(unique)} brands.")
    return unique


def _scrape_brand_models(fetcher: StealthyFetcher, slug: str) -> list[str]:
    """Scrape a brand page to get camera model names.

    Returns list of model name strings.
    """
    url = f"{BASE_URL}{slug}/"
    page = fetcher.fetch(url)
    if page.status != 200:
        print(f"  Failed to fetch {url}: HTTP {page.status}")
        return []

    models = []
    # Model links point to /cameras/{brand}/{model}/
    for link in page.css("a[href]"):
        href = link.attrib.get("href", "")
        m = re.match(rf"^/cameras/{re.escape(slug)}/([^/]+)/?$", href)
        if not m:
            continue
        name = link.text.strip() if link.text else ""
        if name:
            models.append(name)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for name in models:
        if name not in seen:
            seen.add(name)
            unique.append(name)

    return unique


def _collect() -> None:
    """Main collection function."""
    fetcher = StealthyFetcher()

    brands = _scrape_brands(fetcher)
    if not brands:
        print("No brands found. Flickr may be blocking requests.")
        return

    analogue_cameras: list[Camera] = []
    uncertain_cameras: list[Camera] = []
    total_digital = 0
    total_uncertain = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    for i, brand in enumerate(brands, 1):
        brand_name = brand["name"]
        brand_slug = brand["slug"]
        print(f"Processing brand {brand_name} ({i}/{len(brands)})...")

        time.sleep(3)  # Generous delay between requests

        models = _scrape_brand_models(fetcher, brand_slug)
        if not models:
            print(f"  No models found for {brand_name}")
            continue

        manufacturer_norm = normalize_manufacturer(brand_name)

        for model_name in models:
            full_name = f"{brand_name} {model_name}"
            classification = _classify(full_name)

            if classification == "digital":
                total_digital += 1
                continue

            camera = Camera(
                name=model_name,
                manufacturer=brand_name,
                manufacturer_normalized=manufacturer_norm,
                flickr_id=f"{brand_slug}:{model_name}",
                sources=[
                    SourceReference(
                        source="flickr",
                        source_id=f"{brand_slug}:{model_name}",
                        source_url=f"{BASE_URL}{brand_slug}/",
                        retrieved_at=now_iso,
                    )
                ],
            )

            if classification == "analogue":
                analogue_cameras.append(camera)
            else:
                uncertain_cameras.append(camera)
                total_uncertain += 1

    # Include uncertain cameras (better to have false positives)
    all_cameras = analogue_cameras + uncertain_cameras

    print(
        f"\nFound {len(analogue_cameras)} analogue cameras, "
        f"excluded {total_digital} digital cameras"
    )
    if total_uncertain:
        print(f"{total_uncertain} cameras flagged as uncertain (included)")

    save_records(all_cameras, source="flickr", entity_type="cameras")

    # Save uncertain list separately for manual review
    if uncertain_cameras:
        save_records(
            uncertain_cameras,
            source="flickr",
            entity_type="cameras_uncertain",
        )


def main() -> None:
    _collect()


if __name__ == "__main__":
    main()
