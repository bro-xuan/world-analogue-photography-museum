#!/usr/bin/env python3
"""Generate camera detail data for individual camera pages."""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")


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


def main():
    data_path = Path("data/merged/cameras.json")
    if not data_path.exists():
        print(f"ERROR: {data_path} not found")
        sys.exit(1)

    cameras = json.loads(data_path.read_text())
    print(f"Loaded {len(cameras)} cameras")

    detail_map: dict[str, dict] = {}
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

        # Source URLs for attribution
        source_urls = []
        for src in cam.get("sources", []):
            url = src.get("source_url")
            if url:
                source_urls.append({"name": src.get("source", ""), "url": url})

        entry = {
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
            "sources": source_urls if source_urls else None,
            "priceLaunch": cam.get("price_launch_usd"),
            "priceMarket": cam.get("price_market_usd"),
        }

        # Remove None values
        entry = {k: v for k, v in entry.items() if v is not None}

        detail_map[short_id] = entry

    out_path = Path("web/public/data/cameras_detail.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(detail_map, ensure_ascii=False, separators=(",", ":")))

    print(f"\nWrote {out_path}")
    print(f"  Cameras with detail pages: {len(detail_map)}")
    print(f"  Skipped (no description): {skipped_no_desc}")
    print(f"  Skipped (no image): {skipped_no_img}")


if __name__ == "__main__":
    main()
