"""Main price enrichment pipeline for camera data."""

from __future__ import annotations

import json

from src.pricing.inflation import adjust_for_inflation, convert_to_usd
from src.pricing.launch_prices import LAUNCH_PRICES, lookup_launch_price
from src.utils.data_io import MERGED_DIR


def _purge_placeholder_market_prices(cameras: list[dict]) -> int:
    """Remove $1 placeholder market prices from collectiblend. Returns count purged."""
    count = 0
    for cam in cameras:
        if cam.get("price_market_usd") == 1.0:
            cam["price_market_usd"] = None
            cam["price_market_source"] = None
            count += 1
    return count


def _apply_curated_prices(cameras: list[dict]) -> int:
    """Apply curated launch prices from the database. Returns count of prices applied.

    Curated prices ALWAYS override other sources (chinesecamera, llm) since they are
    manually verified from historical records.
    """
    count = 0
    for cam in cameras:
        mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
        name = cam.get("name", "")

        result = lookup_launch_price(mfr, name)
        if result:
            price, currency, year = result
            if currency == "USD":
                cam["price_launch_usd"] = round(price, 2)
            else:
                try:
                    usd_price = convert_to_usd(price, currency, year)
                    cam["price_launch_usd"] = round(usd_price, 2)
                except Exception:
                    continue
            cam["price_launch_currency"] = currency
            cam["price_launch_source"] = "curated"
            count += 1
        elif cam.get("price_launch_usd") and not cam.get("price_launch_source"):
            # Tag existing prices that came from chinesecamera collector
            cam["price_launch_source"] = "chinesecamera"
    return count


def _apply_chinesecamera_prices(cameras: list[dict]) -> int:
    """Apply prices from chinesecamera.com raw data (already in cameras from collector).

    For cameras that already got price_launch_usd from the collector, this is a no-op.
    For cameras from other sources that match chinesecamera data, apply from raw data.
    """
    # Load raw chinesecamera data to get CNY prices
    raw_path = MERGED_DIR.parent / "raw" / "chinesecamera" / "cameras.json"
    if not raw_path.exists():
        return 0

    raw_cameras = json.loads(raw_path.read_text())

    # Build lookup by normalized name
    cn_prices: dict[str, tuple[float, int]] = {}
    for rc in raw_cameras:
        if rc.get("price_launch_usd") and rc.get("year_introduced"):
            key = rc.get("name", "").lower().strip()
            cn_prices[key] = (rc["price_launch_usd"], rc["year_introduced"])

    count = 0
    for cam in cameras:
        if cam.get("price_launch_usd"):
            continue

        name_lower = cam.get("name", "").lower().strip()
        if name_lower in cn_prices:
            cam["price_launch_usd"] = cn_prices[name_lower][0]
            cam["price_launch_currency"] = "CNY"
            cam["price_launch_source"] = "chinesecamera"
            count += 1

    return count


def _tag_existing_market_sources(cameras: list[dict]) -> int:
    """Tag existing market prices that lack a source as collectiblend."""
    count = 0
    for cam in cameras:
        if cam.get("price_market_usd") and not cam.get("price_market_source"):
            cam["price_market_source"] = "collectiblend"
            count += 1
    return count


def _apply_inflation_adjustment(cameras: list[dict]) -> int:
    """Calculate inflation-adjusted prices for all cameras with launch prices."""
    count = 0
    for cam in cameras:
        if not cam.get("price_launch_usd"):
            continue

        year = cam.get("year_introduced")
        if not year:
            # Fall back to the year from the curated price entry
            mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
            name = cam.get("name", "")
            result = lookup_launch_price(mfr, name)
            if result:
                year = result[2]
        if not year:
            continue

        try:
            adjusted = adjust_for_inflation(
                cam["price_launch_usd"],
                year,
            )
            cam["price_adjusted_usd"] = round(adjusted, 2)
            count += 1
        except Exception:
            continue

    return count


def enrich_prices() -> None:
    """Add pricing data to all merged cameras."""
    cameras_path = MERGED_DIR / "cameras.json"
    if not cameras_path.exists():
        print("No merged cameras file found. Run merge first.")
        return

    cameras = json.loads(cameras_path.read_text())
    print(f"Loaded {len(cameras)} cameras from {cameras_path}")

    # Phase 0: Purge $1 placeholder market prices
    print("\nPhase 0: Purging $1 placeholder market prices...")
    purged = _purge_placeholder_market_prices(cameras)
    print(f"  Purged {purged} placeholder prices")

    # Phase 1: Apply curated launch prices
    print("\nPhase 1: Applying curated launch prices...")
    curated_count = _apply_curated_prices(cameras)
    print(f"  Applied {curated_count} curated launch prices")

    # Phase 2: Apply chinesecamera.com prices
    print("\nPhase 2: Applying chinesecamera.com prices...")
    cn_count = _apply_chinesecamera_prices(cameras)
    print(f"  Applied {cn_count} chinesecamera.com prices")

    # Phase 3: Tag existing market price sources
    print("\nPhase 3: Tagging market price sources...")
    tagged = _tag_existing_market_sources(cameras)
    print(f"  Tagged {tagged} existing market prices as collectiblend")

    # Phase 4: Calculate inflation-adjusted prices
    print("\nPhase 4: Calculating inflation-adjusted prices...")
    adj_count = _apply_inflation_adjustment(cameras)
    print(f"  Calculated {adj_count} inflation-adjusted prices")

    # Summary
    with_launch = sum(1 for c in cameras if c.get("price_launch_usd"))
    with_adjusted = sum(1 for c in cameras if c.get("price_adjusted_usd"))
    with_market = sum(1 for c in cameras if c.get("price_market_usd"))

    print(f"\n{'='*60}")
    print("PRICE ENRICHMENT SUMMARY")
    print(f"{'='*60}")
    print(f"Total cameras:          {len(cameras)}")
    print(f"With launch price:      {with_launch} ({with_launch/len(cameras)*100:.1f}%)")
    print(f"With adjusted price:    {with_adjusted} ({with_adjusted/len(cameras)*100:.1f}%)")
    print(f"With market value:      {with_market} ({with_market/len(cameras)*100:.1f}%)")

    # Spot check some well-known cameras
    print(f"\nSpot checks:")
    spot_checks = [
        ("Nikon", "Nikon F"),
        ("Canon", "Canon AE-1"),
        ("Leica", "Leica M3"),
        ("Hasselblad", "Hasselblad 500C"),
        ("Pentax", "Pentax K1000"),
        ("FED", "FED 2"),
    ]
    for mfr, name in spot_checks:
        for cam in cameras:
            if cam.get("manufacturer_normalized") == mfr and cam.get("name", "").lower() == name.lower():
                launch = cam.get("price_launch_usd", "N/A")
                adjusted = cam.get("price_adjusted_usd", "N/A")
                market = cam.get("price_market_usd", "N/A")
                year = cam.get("year_introduced", "?")
                src = cam.get("price_launch_source", "?")
                print(f"  {name} ({year}): launch=${launch} [{src}], adjusted=${adjusted}, market=${market}")
                break

    # Save enriched data
    cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"\nSaved enriched cameras to {cameras_path}")


def main() -> None:
    """Entry point for price enrichment."""
    enrich_prices()


if __name__ == "__main__":
    main()
