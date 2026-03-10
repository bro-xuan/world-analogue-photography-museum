#!/usr/bin/env python3
"""Generate brands.json: brand listing with per-brand camera arrays."""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

# ---------------------------------------------------------------------------
# Helpers (reused from prepare_landing_data.py)
# ---------------------------------------------------------------------------

def _has_image_on_disk(cam: dict) -> str | None:
    """Return the first local_path that exists on disk, or None."""
    for img in cam.get("images", []):
        lp = img.get("local_path")
        if lp and Path(lp).exists():
            return lp
    return None


def _display_name(cam: dict) -> str:
    """Combine manufacturer + name if name doesn't already start with manufacturer."""
    name = cam["name"]
    mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer") or ""
    if mfr and not name.lower().startswith(mfr.lower()):
        return f"{mfr} {name}"
    return name


def _image_path(local_path: str) -> str:
    """Strip 'data/images/' prefix for web-relative path."""
    prefix = "data/images/"
    if local_path.startswith(prefix):
        return local_path[len(prefix):]
    return local_path


def _brand_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------------------
# Region mapping
# ---------------------------------------------------------------------------

_COUNTRY_REGION = {
    "Japan": "Japan",
    "Germany": "Germany",
    "United States": "USA",
    "USA": "USA",
    "China": "China",
    "Russia": "Soviet & Eastern Europe",
    "Soviet Union": "Soviet & Eastern Europe",
    "USSR": "Soviet & Eastern Europe",
    "Ukraine": "Soviet & Eastern Europe",
    "Czech Republic": "Soviet & Eastern Europe",
    "Czechoslovakia": "Soviet & Eastern Europe",
    "East Germany": "Soviet & Eastern Europe",
    "DDR": "Soviet & Eastern Europe",
    "Poland": "Soviet & Eastern Europe",
    "Hungary": "Soviet & Eastern Europe",
    "Romania": "Soviet & Eastern Europe",
    "United Kingdom": "Western Europe",
    "UK": "Western Europe",
    "France": "Western Europe",
    "Italy": "Western Europe",
    "Switzerland": "Western Europe",
    "Austria": "Western Europe",
    "Sweden": "Western Europe",
    "Netherlands": "Western Europe",
    "Belgium": "Western Europe",
    "Denmark": "Western Europe",
    "Spain": "Western Europe",
}

# Preferred region display order
_REGION_ORDER = [
    "Japan",
    "Germany",
    "USA",
    "Western Europe",
    "Soviet & Eastern Europe",
    "China",
    "Other",
]


def _get_region(country: str | None) -> str:
    if not country:
        return "Other"
    return _COUNTRY_REGION.get(country, "Other")


# ---------------------------------------------------------------------------
# Hero image scoring
# ---------------------------------------------------------------------------

def _hero_score(cam: dict) -> int:
    """Score a camera for hero image selection."""
    s = 0
    source_names = {src.get("source", "") for src in cam.get("sources", [])}
    if "wikipedia" in source_names:
        s += 30
    if cam.get("wikidata_qid"):
        s += 10
    s += len(cam.get("description") or "")
    return s


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    data_path = Path("data/merged/cameras.json")
    if not data_path.exists():
        print(f"ERROR: {data_path} not found")
        sys.exit(1)

    cameras = json.loads(data_path.read_text())
    print(f"Loaded {len(cameras)} cameras")

    # Load detail IDs for hasDetail flag
    detail_path = Path("web/public/data/cameras_detail.json")
    detail_ids: set[str] = set()
    if detail_path.exists():
        detail_ids = set(json.loads(detail_path.read_text()).keys())
        print(f"Loaded {len(detail_ids)} detail IDs")

    # Group cameras by brand (manufacturer_normalized), only those with images
    brands: dict[str, dict] = {}  # brand_name -> brand info
    skipped = 0

    for cam in cameras:
        local_path = _has_image_on_disk(cam)
        if not local_path:
            skipped += 1
            continue

        mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer") or ""
        if not mfr:
            skipped += 1
            continue

        cam_id = cam.get("id") or cam["name"]
        name = _display_name(cam)
        img = _image_path(local_path)

        entry = {
            "id": cam_id[:8] if len(cam_id) > 8 else cam_id,
            "name": name,
            "manufacturer": mfr,
        }
        if cam.get("year_introduced"):
            entry["year"] = cam["year_introduced"]
        if cam.get("film_format"):
            entry["format"] = cam["film_format"]
        if cam.get("manufacturer_country"):
            entry["country"] = cam["manufacturer_country"]
        entry["tier"] = "m"  # default tier for brand pages
        entry["image"] = img

        # Thumbnail
        thumb_path = Path(local_path).parent / "thumb.webp"
        if thumb_path.exists():
            entry["thumb"] = _image_path(str(thumb_path))

        # hasDetail
        if entry["id"] in detail_ids:
            entry["hasDetail"] = True

        # Hero scoring
        hero_s = _hero_score(cam)

        if mfr not in brands:
            brands[mfr] = {
                "name": mfr,
                "country": cam.get("manufacturer_country") or "",
                "cameras": [],
                "hero_score": -1,
                "hero_image": None,
            }

        brands[mfr]["cameras"].append(entry)
        if hero_s > brands[mfr]["hero_score"]:
            brands[mfr]["hero_score"] = hero_s
            brands[mfr]["hero_image"] = img

    print(f"Skipped {skipped} cameras (no image or no manufacturer)")
    print(f"Found {len(brands)} brands with images")

    # Build brand entries
    all_brands = []
    for mfr, info in brands.items():
        cams = info["cameras"]
        # Sort cameras by year ascending (None at end)
        cams.sort(key=lambda c: (c.get("year") is None, c.get("year") or 9999))

        years = [c["year"] for c in cams if c.get("year")]
        slug = _brand_slug(mfr)
        region = _get_region(info["country"])

        # Check for logo
        logo_path = Path(f"web/public/logos/{slug}.png")
        logo = f"logos/{slug}.png" if logo_path.exists() else None

        brand_entry = {
            "slug": slug,
            "name": mfr,
            "country": info["country"],
            "region": region,
            "cameraCount": len(cams),
            "heroImage": info["hero_image"],
            "cameras": cams,
        }
        if logo:
            brand_entry["logo"] = logo
        if years:
            brand_entry["yearStart"] = min(years)
            brand_entry["yearEnd"] = max(years)

        all_brands.append(brand_entry)

    # Sort all brands by camera count descending
    all_brands.sort(key=lambda b: -b["cameraCount"])

    # Group by region
    region_map: dict[str, list[dict]] = {}
    for brand in all_brands:
        r = brand["region"]
        if r not in region_map:
            region_map[r] = []
        region_map[r].append(brand)

    # Build regions in preferred order
    regions = []
    for region_name in _REGION_ORDER:
        if region_name in region_map:
            region_brands = region_map[region_name]
            # Sort by camera count within region
            region_brands.sort(key=lambda b: -b["cameraCount"])
            regions.append({
                "name": region_name,
                "count": len(region_brands),
                "brands": region_brands,
            })

    # Any regions not in preferred order
    for region_name, region_brands in region_map.items():
        if region_name not in _REGION_ORDER:
            region_brands.sort(key=lambda b: -b["cameraCount"])
            regions.append({
                "name": region_name,
                "count": len(region_brands),
                "brands": region_brands,
            })

    output = {
        "meta": {
            "total": len(all_brands),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "regions": regions,
        "allBrands": all_brands,
    }

    out_path = Path("web/public/data/brands.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")))

    total_cams = sum(b["cameraCount"] for b in all_brands)
    print(f"\nWrote {out_path}")
    print(f"  {len(all_brands)} brands, {total_cams} cameras with images")
    print(f"\n  Regions:")
    for r in regions:
        print(f"    {r['name']}: {r['count']} brands")


if __name__ == "__main__":
    main()
