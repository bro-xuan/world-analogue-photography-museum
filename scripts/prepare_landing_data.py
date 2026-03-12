#!/usr/bin/env python3
"""Prepare landing page data: score cameras and generate landing.json."""

import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

# ---------------------------------------------------------------------------
# Curated legendary cameras: (display_name, name_match, manufacturer_hint)
# ---------------------------------------------------------------------------
CURATED_CAMERAS = [
    ("Hasselblad 500C/M", "500 C/M", "Hasselblad"),
    ("Hasselblad 500C", "500 C", "Hasselblad"),
    ("Hasselblad SWC", "Super Wide C (SWC)", "Hasselblad"),
    ("Leica M3", "Leica M3", None),
    ("Leica M6", "Leica M6", None),
    ("Leica IIIf", "Leica IIIf", None),
    ("Nikon F", "Nikon F (eyelevel, chrome)", None),
    ("Nikon F2", "Nikon F2", None),
    ("Nikon F3", "Nikon F3", None),
    ("Nikon SP", "Nikon SP", None),
    ("Canon AE-1", "Canon AE-1", None),
    ("Canon F-1", "Canon F-1", None),
    ("Canon P", "Canon P", None),
    ("Rolleiflex 2.8F", "Rolleiflex 2.8F", None),
    ("Rollei 35", "Rollei 35", None),
    ("Pentax K1000", "Pentax K1000", None),
    ("Pentax 67", "Pentax 6x7", None),
    ("Pentax Spotmatic", "Pentax Spotmatic", None),
    ("Olympus OM-1", "Olympus OM-1", None),
    ("Olympus Pen F", "Olympus Pen F", None),
    ("Contax T2", "Contax T2", None),
    ("Contax T3", "Contax T3", None),
    ("Mamiya RB67", "Mamiya RB67", None),
    ("Mamiya C330", "C330", None),
    ("Yashica Electro 35", "Yashica Electro 35", None),
    ("Polaroid SX-70", "Polaroid SX-70", None),
    ("Minolta CLE", "Minolta CLE", None),
    ("Argus C3", "Argus C3", None),
    ("Holga", "Holga", None),
    ("Lomo LC-A", "Lomo LC-A", None),
    ("Kodak Brownie", "Kodak Brownie", None),
    ("Kodak 35", "Kodak 35", None),
    ("Zeiss Ikon Kolibri", "Zeiss Ikon Kolibri", "Zeiss"),
]

PRESTIGE_BRANDS = {
    b.lower()
    for b in [
        "Leica",
        "Hasselblad",
        "Nikon",
        "Canon",
        "Rollei",
        "Contax",
        "Pentax",
        "Olympus",
        "Mamiya",
        "Polaroid",
        "Voigtlander",
        "Zeiss",
        "Bronica",
        "Linhof",
        "Graflex",
        "Fujifilm",
        "Minolta",
        "Yashica",
        "Ricoh",
    ]
}


def _has_image_on_disk(cam: dict) -> str | None:
    """Return the first local_path that exists on disk, or None."""
    for img in cam.get("images", []):
        lp = img.get("local_path")
        if lp and Path(lp).exists():
            return lp
    return None


def _find_curated(cameras: list[dict]) -> dict[str, tuple[dict, str]]:
    """Return {camera_id: (camera_dict, display_name)} for curated cameras."""
    matched: dict[str, tuple[dict, str]] = {}

    for display_name, name_match, mfr_hint in CURATED_CAMERAS:
        pool = cameras
        if mfr_hint:
            pool = [
                c
                for c in cameras
                if mfr_hint.lower() in (c.get("manufacturer") or "").lower()
                or mfr_hint.lower()
                in (c.get("manufacturer_normalized") or "").lower()
            ]

        # 1. Exact name match
        candidates = [c for c in pool if c["name"] == name_match]
        # 2. name.startswith
        if not candidates:
            candidates = [c for c in pool if c["name"].startswith(name_match)]
        # 3. substring
        if not candidates:
            candidates = [c for c in pool if name_match in c["name"]]

        if candidates:
            # Pick shortest name to prefer the base variant
            best = min(candidates, key=lambda c: len(c["name"]))
            cam_id = best.get("id") or best["name"]
            matched[cam_id] = (best, display_name)
        else:
            print(f"  WARNING: curated camera not found: {display_name!r} (match={name_match!r})")

    return matched


def _is_prestige(cam: dict) -> bool:
    mfr = (cam.get("manufacturer_normalized") or cam.get("manufacturer") or "").lower()
    return any(brand in mfr for brand in PRESTIGE_BRANDS)


def _score(cam: dict, has_image: bool) -> int:
    """Score a non-curated camera on a 0-99 scale."""
    s = 0

    source_names = {src.get("source", "") for src in cam.get("sources", [])}

    # Wikipedia source
    if "wikipedia" in source_names:
        s += 30

    # Wikidata QID
    if cam.get("wikidata_qid"):
        s += 10

    # Extra sources beyond 1
    n_sources = len(cam.get("sources", []))
    if n_sources > 1:
        s += min((n_sources - 1) * 15, 30)

    # Description length
    desc_len = len(cam.get("description") or "")
    if desc_len > 200:
        s += 15
    elif desc_len > 150:
        s += 10
    elif desc_len > 100:
        s += 5

    # Prestige brand
    if _is_prestige(cam):
        s += 5

    # Has image on disk
    if has_image:
        s += 5

    # Multiple images
    if len(cam.get("images", [])) > 1:
        s += 3

    # Has year
    if cam.get("year_introduced"):
        s += 2

    return min(s, 99)


def _display_name(cam: dict) -> str:
    """Combine manufacturer + name if name doesn't already start with manufacturer."""
    name = cam["name"]
    # Prefer normalized (short) manufacturer for display
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


HERO_COLS = 3
HERO_ROWS = 2


def _compute_grid(n: int) -> tuple[int, int, list[int], list[tuple[int, int]]]:
    """Replicate FreeCanvas.tsx grid geometry.

    Returns (cols, rows, indices_by_distance, cell_positions) where:
    - indices_by_distance[k] = row-major index of the k-th closest active cell
    - cell_positions[i] = (col, row) of the i-th non-hero cell in row-major order
    Only the first n non-hero cells are "active" (matching FreeCanvas.tsx's
    cameras[ci] assignment which stops at ci < cameras.length).
    """
    # Need enough cells for n cameras PLUS the hero area
    total_needed = n + HERO_COLS * HERO_ROWS
    cols = math.ceil(math.sqrt(total_needed))
    rows = math.ceil(total_needed / cols)

    hero_col_start = (cols - HERO_COLS) // 2 + 1
    hero_row_start = (rows - HERO_ROWS) // 2 + 1

    # Hero center (in grid coordinates)
    hero_cx = hero_col_start + HERO_COLS / 2 - 0.5
    hero_cy = hero_row_start + HERO_ROWS / 2 - 0.5

    # Enumerate non-hero cells in row-major order (matching FreeCanvas.tsx)
    cell_positions: list[tuple[int, int]] = []
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            in_hero = (
                hero_col_start <= c < hero_col_start + HERO_COLS
                and hero_row_start <= r < hero_row_start + HERO_ROWS
            )
            if not in_hero:
                cell_positions.append((c, r))

    # Only rank the first n cells (the ones FreeCanvas.tsx actually uses)
    active = cell_positions[:n]
    ranked = []
    for i, (c, r) in enumerate(active):
        dist = math.sqrt((c - hero_cx) ** 2 + (r - hero_cy) ** 2)
        angle = math.atan2(r - hero_cy, c - hero_cx)
        ranked.append((dist, angle, i))

    # Sort by distance, then angle for spiral tie-breaking
    ranked.sort()

    return cols, rows, [i for _, _, i in ranked], cell_positions


def _diversify(cameras: list[dict], min_gap: int) -> list[dict]:
    """Reorder cameras so no same-brand cameras appear within min_gap positions."""
    if not cameras:
        return []

    result = []
    remaining = list(cameras)

    while remaining:
        # Look at recent brands in the result tail
        recent_brands = set()
        for entry in result[-min_gap:]:
            recent_brands.add(entry.get("manufacturer", "").lower())

        # Find first candidate that doesn't clash
        placed = False
        for i, cam in enumerate(remaining):
            brand = cam.get("manufacturer", "").lower()
            if brand not in recent_brands:
                result.append(remaining.pop(i))
                placed = True
                break

        if not placed:
            # No non-clashing candidate; just take the first one
            result.append(remaining.pop(0))

    return result


def _arrange_by_distance(
    xl: list[dict], l_list: list[dict], m: list[dict]
) -> list[dict]:
    """Place cameras by distance from hero: XL closest, then L, then M.

    Returns cameras in row-major order matching FreeCanvas.tsx's sequential
    cameras[ci] assignment to non-hero cells.
    """
    # Build priority list: diversified XL + diversified L + shuffled M
    priority = _diversify(xl, min_gap=3) + _diversify(l_list, min_gap=2) + m

    n = len(priority)
    cols, rows, indices_by_distance, cell_positions = _compute_grid(n)

    # Assign: priority[k] → output slot at row-major index of k-th closest cell
    # Every slot gets exactly one camera (n priorities fill n active cells)
    output: list[dict | None] = [None] * n
    for k, cam in enumerate(priority):
        output[indices_by_distance[k]] = cam

    # Print distance stats for XL cameras
    if xl:
        hero_col_start = (cols - HERO_COLS) // 2 + 1
        hero_row_start = (rows - HERO_ROWS) // 2 + 1
        hero_cx = hero_col_start + HERO_COLS / 2 - 0.5
        hero_cy = hero_row_start + HERO_ROWS / 2 - 0.5

        xl_dists = []
        for k in range(len(xl)):
            rm_idx = indices_by_distance[k]
            c, r = cell_positions[rm_idx]
            d = math.sqrt((c - hero_cx) ** 2 + (r - hero_cy) ** 2)
            xl_dists.append(d)
        print(f"\n  XL distance range: {min(xl_dists):.1f} – {max(xl_dists):.1f}")

    return output  # type: ignore[return-value]


def main():
    data_path = Path("data/merged/cameras.json")
    if not data_path.exists():
        print(f"ERROR: {data_path} not found")
        sys.exit(1)

    cameras = json.loads(data_path.read_text())
    print(f"Loaded {len(cameras)} cameras")

    # Find curated cameras
    curated = _find_curated(cameras)
    curated_ids = set(curated.keys())
    print(f"Matched {len(curated)}/{len(CURATED_CAMERAS)} curated cameras")

    # Score every camera and classify
    xl_entries = []
    l_entries = []
    m_entries = []
    hidden_count = 0
    curated_no_image = []

    for cam in cameras:
        cam_id = cam.get("id") or cam["name"]
        local_path = _has_image_on_disk(cam)

        if cam_id in curated_ids:
            _, display = curated[cam_id]
            score = 100
            tier = "xl"
            if not local_path:
                curated_no_image.append(display)
                hidden_count += 1
                continue
            name = display
        else:
            has_image = local_path is not None
            score = _score(cam, has_image)

            if score == 0 or not local_path:
                hidden_count += 1
                continue

            if score >= 35:
                tier = "l"
            else:
                tier = "m"

            name = _display_name(cam)

        entry = {
            "id": cam_id[:8] if len(cam_id) > 8 else cam_id,
            "name": name,
            "manufacturer": cam.get("manufacturer_normalized") or cam.get("manufacturer") or "",
        }
        if cam.get("year_introduced"):
            entry["year"] = cam["year_introduced"]
        if cam.get("film_format"):
            entry["format"] = cam["film_format"]
        if cam.get("manufacturer_country"):
            entry["country"] = cam["manufacturer_country"]
        entry["tier"] = tier
        entry["image"] = _image_path(local_path)

        # Add thumbnail path if it exists on disk
        thumb_path = Path(local_path).parent / "thumb.webp"
        if thumb_path.exists():
            entry["thumb"] = _image_path(str(thumb_path))

        if tier == "xl":
            xl_entries.append(entry)
        elif tier == "l":
            l_entries.append(entry)
        else:
            m_entries.append(entry)

    # Print curated cameras missing or without images
    if curated_no_image:
        print(f"\nCurated cameras with no image on disk:")
        for name in curated_no_image:
            print(f"  - {name}")

    missing_curated = set(d for d, _, _ in CURATED_CAMERAS) - set(
        display for _, display in curated.values()
    )
    if missing_curated:
        print(f"\nCurated cameras not found in data:")
        for name in sorted(missing_curated):
            print(f"  - {name}")

    # Sort XL by curated importance (CURATED_CAMERAS order)
    curated_order = {display: i for i, (display, _, _) in enumerate(CURATED_CAMERAS)}
    xl_entries.sort(key=lambda e: curated_order.get(e["name"], len(CURATED_CAMERAS)))

    # Shuffle M tier for variety; XL and L get diversified in _arrange_by_distance
    random.seed(42)
    random.shuffle(m_entries)

    # Place cameras by distance from hero center
    final = _arrange_by_distance(xl_entries, l_entries, m_entries)

    total_shown = len(final)

    # Load detail IDs so we can mark which cameras have detail pages
    detail_path = Path("web/public/data/cameras_detail.json")
    detail_ids: set[str] = set()
    if detail_path.exists():
        detail_ids = set(json.loads(detail_path.read_text()).keys())
        print(f"Loaded {len(detail_ids)} detail IDs from {detail_path}")
    else:
        print(f"WARNING: {detail_path} not found — hasDetail will be False for all")

    # Tag entries with hasDetail
    for entry in final:
        if entry["id"] in detail_ids:
            entry["hasDetail"] = True

    output = {
        "meta": {
            "total": total_shown,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "cameras": final,
    }

    out_path = Path("web/public/data/landing.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    print(f"\nWrote {out_path} ({total_shown} cameras)")

    # Tier distribution summary
    print(f"\nTier distribution:")
    print(f"  XL: {len(xl_entries)} (score=100, curated)")
    print(f"  L:  {len(l_entries)} (score 35-99)")
    print(f"  M:  {len(m_entries)} (score 1-39)")
    print(f"  Hidden: {hidden_count} (no image or score=0)")
    print(f"  Total shown: {total_shown}")


if __name__ == "__main__":
    main()
