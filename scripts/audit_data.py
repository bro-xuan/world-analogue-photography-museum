"""Data quality audit for camera records.

Produces console output with coverage stats and generates report files in data/reports/.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.data_io import MERGED_DIR

REPORTS_DIR = MERGED_DIR.parent / "reports"

# Patterns for suspected digital cameras that slipped through
_DIGITAL_SUSPECTS = [
    re.compile(r"\bOlympus\s+C-\d{3,4}", re.I),
    re.compile(r"\bCamedia\b", re.I),
    re.compile(r"\bLeica\s+X\s+Vario\b", re.I),
    re.compile(r"\bLeica\s+[XQ]\d?\b", re.I),
    re.compile(r"\bLeica\s+SL\d?\b", re.I),
    re.compile(r"\bLeica\s+TL\d?\b", re.I),
    # Note: Leica CL (1973) is a film camera — don't flag it. Only flag known digital Leica CL variants.
    re.compile(r"\bFinePix\s+[FZJ]\d", re.I),
    re.compile(r"\bCoolPix\s+[LSP]\d", re.I),
    re.compile(r"\bCyber-shot\s+DSC\b", re.I),
    re.compile(r"\bdigital\b", re.I),
    re.compile(r"\bDSLR\b", re.I),
    re.compile(r"\bmirrorless\b", re.I),
    re.compile(r"\bStill image camera with motion capability\b", re.I),
]


def _is_useless_description(desc: str | None) -> bool:
    if not desc:
        return True
    if desc.startswith("Wikimedia Commons category"):
        return True
    if len(desc.strip()) < 5:
        return True
    return False


def audit_cameras():
    cameras_path = MERGED_DIR / "cameras.json"
    if not cameras_path.exists():
        print("No merged cameras file found.")
        return

    cameras = json.loads(cameras_path.read_text())
    total = len(cameras)
    print(f"\n{'='*60}")
    print(f"DATA QUALITY AUDIT — {total} cameras")
    print(f"{'='*60}\n")

    # Field coverage
    has_images = sum(1 for c in cameras if c.get("images"))
    has_description = sum(1 for c in cameras if not _is_useless_description(c.get("description")))
    has_type = sum(1 for c in cameras if c.get("camera_type") and c["camera_type"].lower() != "camera")
    has_year = sum(1 for c in cameras if c.get("year_introduced"))
    has_format = sum(1 for c in cameras if c.get("film_format"))
    has_country = sum(1 for c in cameras if c.get("manufacturer_country"))
    has_mfr_norm = sum(1 for c in cameras if c.get("manufacturer_normalized"))
    has_local_img = sum(1 for c in cameras if any(img.get("local_path") for img in c.get("images", [])))

    print("FIELD COVERAGE:")
    print(f"  {'Field':<30} {'Count':>6} {'Coverage':>8}")
    print(f"  {'-'*30} {'-'*6} {'-'*8}")
    for label, count in [
        ("images (any URL)", has_images),
        ("images (downloaded)", has_local_img),
        ("description (useful)", has_description),
        ("camera_type (non-generic)", has_type),
        ("year_introduced", has_year),
        ("film_format", has_format),
        ("manufacturer_country", has_country),
        ("manufacturer_normalized", has_mfr_norm),
    ]:
        pct = count / total * 100 if total else 0
        print(f"  {label:<30} {count:>6} {pct:>7.1f}%")

    # Source distribution
    source_counter: Counter = Counter()
    for c in cameras:
        for src in c.get("sources", []):
            source_counter[src.get("source", "unknown")] += 1
    print(f"\nSOURCE DISTRIBUTION:")
    for src, cnt in source_counter.most_common():
        print(f"  {src:<20} {cnt:>6}")

    # Country distribution
    country_counter: Counter = Counter()
    for c in cameras:
        country = c.get("manufacturer_country") or "Unknown"
        country_counter[country] += 1
    print(f"\nCOUNTRY DISTRIBUTION:")
    for country, cnt in country_counter.most_common(20):
        print(f"  {country:<20} {cnt:>6}")

    # Suspected digital cameras
    digital_suspects = []
    for c in cameras:
        name = c.get("name", "")
        cam_type = c.get("camera_type", "") or ""
        text = f"{name} {cam_type}"
        for pat in _DIGITAL_SUSPECTS:
            if pat.search(text):
                digital_suspects.append({
                    "id": c.get("id"),
                    "name": name,
                    "manufacturer_normalized": c.get("manufacturer_normalized"),
                    "camera_type": cam_type,
                    "sources": [s.get("source") for s in c.get("sources", [])],
                    "matched_pattern": pat.pattern,
                })
                break

    # Normalization issues
    norm_issues = []
    for c in cameras:
        mfr = c.get("manufacturer", "")
        mfr_norm = c.get("manufacturer_normalized", "")
        if mfr and mfr_norm and mfr == mfr_norm and len(mfr) > 2:
            # Manufacturer wasn't normalized (stayed the same), could be an issue
            # Only flag if it doesn't look like a clean name
            if any(ch in mfr for ch in [".", ",", "(", "\"", "'"]) or mfr.lower() != mfr.title().lower():
                norm_issues.append({
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "manufacturer": mfr,
                    "manufacturer_normalized": mfr_norm,
                    "sources": [s.get("source") for s in c.get("sources", [])],
                })

    # Missing images
    missing_images = []
    for c in cameras:
        if not c.get("images"):
            missing_images.append({
                "id": c.get("id"),
                "name": c.get("name"),
                "manufacturer_normalized": c.get("manufacturer_normalized"),
                "sources": [s.get("source") for s in c.get("sources", [])],
            })

    # Missing descriptions
    missing_descriptions = []
    for c in cameras:
        if _is_useless_description(c.get("description")):
            missing_descriptions.append({
                "id": c.get("id"),
                "name": c.get("name"),
                "manufacturer_normalized": c.get("manufacturer_normalized"),
                "sources": [s.get("source") for s in c.get("sources", [])],
            })

    print(f"\nISSUES FOUND:")
    print(f"  Cameras missing images:       {len(missing_images)}")
    print(f"  Cameras missing descriptions: {len(missing_descriptions)}")
    print(f"  Suspected digital cameras:    {len(digital_suspects)}")
    print(f"  Normalization issues:         {len(norm_issues)}")

    # Save reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    reports = {
        "cameras_missing_images.json": missing_images,
        "cameras_missing_descriptions.json": missing_descriptions,
        "suspected_digital.json": digital_suspects,
        "normalization_issues.json": norm_issues,
        "full_audit_summary.json": {
            "total_cameras": total,
            "field_coverage": {
                "images_any": has_images,
                "images_downloaded": has_local_img,
                "description_useful": has_description,
                "camera_type_specific": has_type,
                "year_introduced": has_year,
                "film_format": has_format,
                "manufacturer_country": has_country,
                "manufacturer_normalized": has_mfr_norm,
            },
            "source_distribution": dict(source_counter.most_common()),
            "country_distribution": dict(country_counter.most_common()),
            "issues": {
                "missing_images": len(missing_images),
                "missing_descriptions": len(missing_descriptions),
                "suspected_digital": len(digital_suspects),
                "normalization_issues": len(norm_issues),
            },
        },
    }

    for filename, data in reports.items():
        path = REPORTS_DIR / filename
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"  Saved {path}")

    print(f"\nReports saved to {REPORTS_DIR}/")


if __name__ == "__main__":
    audit_cameras()
