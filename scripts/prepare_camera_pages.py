#!/usr/bin/env python3
"""Generate camera detail data for individual camera pages."""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

# Normalize raw camera_type values into clean display labels.
_CAMERA_TYPE_MAP: dict[str, str] = {
    "slr": "SLR",
    "tlr": "TLR",
    "rangefinder": "Rangefinder",
    "point-and-shoot": "Point & Shoot",
    "folding": "Folding",
    "box camera": "Box",
    "view camera": "View",
    "instant": "Instant",
    "panoramic": "Panoramic",
    "swing-lens panoramic camera": "Panoramic",
    "35 mm swing-lens panoramic": "Panoramic",
    "stereo": "Stereo",
    "toy camera": "Toy",
    "medium format": "Medium Format",
    "35 mm bridge": "Bridge",
    "subminiature camera": "Subminiature",
    "full frame milc": "Mirrorless",
    "aps-c milc": "Mirrorless",
}


_CAMERA_TYPE_DISPLAY = {v.lower(): v for v in set(_CAMERA_TYPE_MAP.values())}


def _normalize_camera_type(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.lower().strip()
    return _CAMERA_TYPE_MAP.get(key) or _CAMERA_TYPE_DISPLAY.get(key)


def _has_image_on_disk(cam: dict) -> str | None:
    for img in cam.get("images", []):
        lp = img.get("local_path")
        if lp and Path(lp).exists():
            return lp
    return None


def _all_images_on_disk(cam: dict) -> list[str]:
    """Return all local_path values that exist on disk."""
    result = []
    for img in cam.get("images", []):
        lp = img.get("local_path")
        if lp and Path(lp).exists():
            result.append(lp)
    return result


def _image_path(local_path: str) -> str:
    prefix = "data/images/"
    if local_path.startswith(prefix):
        return local_path[len(prefix) :]
    return local_path


def _display_name(cam: dict) -> str:
    name = cam["name"]
    mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer") or ""
    if mfr and not name.lower().startswith(mfr.lower()):
        return f"{mfr} {name}"
    return name


def _build_related_cameras(
    detail_map: dict[str, dict],
    mfr_index: dict[str, list[tuple[str, dict]]],
) -> None:
    """Add relatedCameras to each entry: up to 6 from same manufacturer, sorted by year proximity."""
    for cam_id, entry in detail_map.items():
        mfr = entry.get("manufacturer", "")
        siblings = mfr_index.get(mfr, [])
        if len(siblings) <= 1:
            continue

        cam_year = entry.get("year")

        # Sort siblings by year proximity to this camera
        def sort_key(item: tuple[str, dict]) -> tuple[int, str]:
            sid, sib = item
            if cam_year and sib.get("year"):
                return (abs(sib["year"] - cam_year), sib.get("name", ""))
            # No year: sort to end, alphabetically
            return (999999, sib.get("name", ""))

        related = []
        for sid, sib in sorted(siblings, key=sort_key):
            if sid == cam_id:
                continue
            rel: dict = {"id": sid, "name": sib["name"]}
            if sib.get("images"):
                rel["image"] = sib["images"][0]
            if sib.get("year"):
                rel["year"] = sib["year"]
            related.append(rel)
            if len(related) >= 6:
                break

        if related:
            entry["relatedCameras"] = related


def main():
    data_path = Path("data/merged/cameras.json")
    if not data_path.exists():
        print(f"ERROR: {data_path} not found")
        sys.exit(1)

    cameras = json.loads(data_path.read_text())
    print(f"Loaded {len(cameras)} cameras")

    detail_map: dict[str, dict] = {}
    mfr_index: dict[str, list[tuple[str, dict]]] = {}
    skipped_no_desc = 0
    skipped_no_img = 0

    for cam in cameras:
        images = _all_images_on_disk(cam)
        if not images:
            skipped_no_img += 1
            continue

        desc = (cam.get("description") or "").strip()
        if not desc:
            skipped_no_desc += 1

        cam_id = cam.get("id", "")
        short_id = cam_id[:8] if len(cam_id) > 8 else cam_id

        # Build specs dict (only non-null values)
        specs: dict[str, str | int] = {}
        ct = _normalize_camera_type(cam.get("camera_type"))
        if ct:
            specs["type"] = ct
        if cam.get("film_format"):
            specs["format"] = cam["film_format"]
        if cam.get("lens_mount"):
            specs["lens"] = cam["lens_mount"]
        if cam.get("shutter_speed_range"):
            specs["shutter"] = cam["shutter_speed_range"]
        if cam.get("metering"):
            specs["metering"] = cam["metering"]
        if cam.get("weight_g"):
            specs["weight"] = f"{cam['weight_g']}g"
        if cam.get("dimensions"):
            specs["dimensions"] = cam["dimensions"]
        if cam.get("battery"):
            specs["battery"] = cam["battery"]

        entry: dict = {
            "name": _display_name(cam),
            "manufacturer": cam.get("manufacturer_normalized")
            or cam.get("manufacturer")
            or "",
            "country": cam.get("manufacturer_country") or None,
            "description": desc or None,
            "year": cam.get("year_introduced"),
            "yearEnd": cam.get("year_discontinued"),
            "images": [_image_path(p) for p in images],
            "specs": specs if specs else None,
            "priceLaunch": cam.get("price_launch_usd"),
            "priceMarket": cam.get("price_market_usd"),
            "priceLaunchSource": cam.get("price_launch_source"),
            "priceMarketSource": cam.get("price_market_source"),
        }

        # Ratings (pre-generated editorial scores)
        ratings = cam.get("ratings")
        if ratings:
            entry["ratings"] = ratings

        # Inflation-adjusted price
        pa = cam.get("price_adjusted_usd")
        if pa:
            entry["priceAdjusted"] = round(pa)

        # Remove None values
        entry = {k: v for k, v in entry.items() if v is not None}

        detail_map[short_id] = entry

        # Track manufacturer index for related cameras
        mfr = entry.get("manufacturer", "")
        if mfr:
            mfr_index.setdefault(mfr, []).append((short_id, entry))

    # Second pass: compute related cameras
    _build_related_cameras(detail_map, mfr_index)

    out_path = Path("web/public/data/cameras_detail.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(detail_map, ensure_ascii=False, separators=(",", ":")))

    # Stats
    n_type = sum(1 for e in detail_map.values() if e.get("specs", {}).get("type"))
    n_adj = sum(1 for e in detail_map.values() if "priceAdjusted" in e)
    n_rel = sum(1 for e in detail_map.values() if "relatedCameras" in e)
    n_rat = sum(1 for e in detail_map.values() if "ratings" in e)

    print(f"\nWrote {out_path}")
    print(f"  Cameras with detail pages: {len(detail_map)}")
    print(f"  With type in specs: {n_type}")
    print(f"  With priceAdjusted: {n_adj}")
    print(f"  With relatedCameras: {n_rel}")
    print(f"  With ratings: {n_rat}")
    print(f"  Skipped (no description): {skipped_no_desc}")
    print(f"  Skipped (no image): {skipped_no_img}")


if __name__ == "__main__":
    main()
