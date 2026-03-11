#!/usr/bin/env python3
"""Enrich camera launch prices using an LLM (OpenAI-compatible API).

Targets cameras WITHOUT launch prices. The LLM is asked for the original MSRP.
Results are validated and stored with price_launch_source = "llm".

Usage:
    ZAI_API_KEY=xxx uv run python scripts/enrich_prices_llm.py --limit 500 --workers 3
    OPENAI_API_KEY=xxx uv run python scripts/enrich_prices_llm.py --limit 1000 --workers 10

Validation mode (compare LLM prices against curated prices):
    uv run python scripts/enrich_prices_llm.py --validate --limit 400
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, ".")

import httpx
from openai import OpenAI

from src.pricing.inflation import convert_to_usd
from src.pricing.launch_prices import lookup_launch_price

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

PRICE_PROMPT = """\
What was the original launch MSRP (manufacturer's suggested retail price) of the {name} camera by {manufacturer}, introduced around {year}?

Respond with ONLY a JSON object in this exact format:
{{"price": NNN, "currency": "USD", "year": YYYY}}

Rules:
- price = the original retail price in the ORIGINAL currency it was sold in
- currency = the ISO currency code (USD, JPY, DEM, GBP, EUR, SEK, CNY, SUR for Soviet rubles)
- year = the year the price was from
- If you are not confident about the price, respond with exactly: UNKNOWN
- Body-only prices (without lens) are acceptable for SLR cameras
- Do not guess or make up prices — only respond if you have real knowledge"""


def _parse_price_response(text: str) -> dict | None:
    """Parse LLM response into a price dict, or None if unknown/invalid."""
    text = text.strip()
    if "UNKNOWN" in text.upper():
        return None

    # Try to find JSON in the response
    match = re.search(r'\{[^{}]*"price"[^{}]*\}', text)
    if not match:
        return None

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None

    price = data.get("price")
    currency = data.get("currency", "USD")
    year = data.get("year")

    if not isinstance(price, (int, float)) or price <= 0:
        return None
    if not isinstance(year, int) or year < 1900 or year > 2025:
        return None
    if not isinstance(currency, str) or len(currency) != 3:
        return None

    return {"price": float(price), "currency": currency.upper(), "year": year}


def _convert_to_usd(price: float, currency: str, year: int) -> float | None:
    """Convert a price to USD. Returns None if conversion fails."""
    if currency == "USD":
        return round(price, 2)
    try:
        return convert_to_usd(price, currency, year)
    except (ValueError, KeyError):
        return None


def _query_price(
    cam: dict,
    client: OpenAI,
    model: str,
) -> dict | None:
    """Ask LLM for a camera's launch price. Returns parsed dict or None."""
    name = cam["name"]
    manufacturer = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
    year = cam.get("year_introduced") or "unknown year"

    prompt = PRICE_PROMPT.format(name=name, manufacturer=manufacturer, year=year)

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
                temperature=0.3,
            )
            text = resp.choices[0].message.content.strip()
            if not text:
                return None
            result = _parse_price_response(text)
            if result:
                # Validate: convert to USD and check range
                usd = _convert_to_usd(result["price"], result["currency"], result["year"])
                if usd is None or usd <= 0 or usd > 50000:
                    return None
                result["price_usd"] = usd
            return result
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower():
                wait = (attempt + 1) * 10
                time.sleep(wait)
                continue
            return None
    return None


# ---------------------------------------------------------------------------
# Validation mode
# ---------------------------------------------------------------------------

def _run_validation(cameras: list[dict], client: OpenAI, model: str, limit: int, workers: int) -> None:
    """Compare LLM prices against curated prices to measure accuracy."""
    # Find cameras with curated prices
    curated = []
    for cam in cameras:
        mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
        name = cam.get("name", "")
        result = lookup_launch_price(mfr, name)
        if result:
            price, currency, year = result
            usd = _convert_to_usd(price, currency, year)
            if usd and usd > 0:
                curated.append((cam, usd))

    print(f"Found {len(curated)} cameras with curated prices")
    if limit > 0:
        curated = curated[:limit]
    print(f"Validating {len(curated)}...")

    matches = 0
    close = 0
    misses = 0
    unknowns = 0
    total = len(curated)
    lock = threading.Lock()

    def validate_one(item: tuple[dict, float]) -> tuple[str, float, float | None]:
        cam, curated_usd = item
        result = _query_price(cam, client, model)
        name = cam["name"]
        if result is None:
            return name, curated_usd, None
        return name, curated_usd, result["price_usd"]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(validate_one, item): i for i, item in enumerate(curated)}
        for future in as_completed(futures):
            name, curated_usd, llm_usd = future.result()
            with lock:
                if llm_usd is None:
                    unknowns += 1
                    status = "UNKNOWN"
                else:
                    ratio = llm_usd / curated_usd if curated_usd > 0 else 999
                    if 0.7 <= ratio <= 1.3:
                        matches += 1
                        status = f"MATCH (LLM=${llm_usd:.0f} vs curated=${curated_usd:.0f}, {ratio:.0%})"
                    elif 0.5 <= ratio <= 2.0:
                        close += 1
                        status = f"CLOSE (LLM=${llm_usd:.0f} vs curated=${curated_usd:.0f}, {ratio:.0%})"
                    else:
                        misses += 1
                        status = f"MISS  (LLM=${llm_usd:.0f} vs curated=${curated_usd:.0f}, {ratio:.0%})"

                done = matches + close + misses + unknowns
                print(f"  [{done}/{total}] {name}: {status}", flush=True)

    answered = matches + close + misses
    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"Total tested:    {total}")
    print(f"UNKNOWN:         {unknowns} ({unknowns/total*100:.0f}%)")
    print(f"Answered:        {answered} ({answered/total*100:.0f}%)")
    if answered > 0:
        print(f"  Within 30%:    {matches} ({matches/answered*100:.0f}% of answered)")
        print(f"  Within 50-200%:{close} ({close/answered*100:.0f}% of answered)")
        print(f"  Way off:       {misses} ({misses/answered*100:.0f}% of answered)")
        accuracy = matches / answered * 100
        print(f"\nAccuracy (within 30%): {accuracy:.0f}%")
        if accuracy >= 80:
            print("=> GOOD: LLM prices are reliable enough for direct use")
        elif accuracy >= 60:
            print("=> OK: Consider flagging LLM prices as estimates in UI")
        else:
            print("=> POOR: LLM prices should be flagged as rough estimates")


# ---------------------------------------------------------------------------
# Main enrichment
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Enrich camera launch prices via LLM")
    parser.add_argument("--limit", type=int, default=100, help="Max cameras to process")
    parser.add_argument("--model", default=None, help="LLM model name")
    parser.add_argument("--api-base", default=None, help="Custom OpenAI-compatible API base URL")
    parser.add_argument("--api-key", default=None, help="Custom API key")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent LLM requests")
    parser.add_argument("--validate", action="store_true", help="Compare LLM vs curated prices")
    parser.add_argument("--require-images", action="store_true", help="Skip cameras without images")
    args = parser.parse_args()

    data_path = Path("data/merged/cameras.json")
    if not data_path.exists():
        print(f"ERROR: {data_path} not found")
        sys.exit(1)

    cameras = json.loads(data_path.read_text())
    print(f"Loaded {len(cameras)} cameras")

    # --- Initialize LLM client ---
    api_key = args.api_key
    api_base = args.api_base
    model = args.model

    zai_key = os.environ.get("ZAI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if api_key and api_base:
        model = model or "gpt-4o-mini"
    elif zai_key:
        api_key = zai_key
        api_base = "https://api.z.ai/api/coding/paas/v4/"
        model = model or "glm-4.5-air"
        print(f"LLM provider: Z.ai GLM (model={model})")
    elif openai_key:
        api_key = openai_key
        api_base = None
        model = model or "gpt-4o-mini"
        print(f"LLM provider: OpenAI (model={model})")
    else:
        print("ERROR: No LLM API key found. Set ZAI_API_KEY or OPENAI_API_KEY.")
        sys.exit(1)

    client_kwargs: dict = {"api_key": api_key}
    if api_base:
        client_kwargs["base_url"] = api_base
    client = OpenAI(
        **client_kwargs,
        http_client=httpx.Client(verify=False, timeout=60),
        timeout=60,
    )

    # --- Validation mode ---
    if args.validate:
        _run_validation(cameras, client, model, args.limit, args.workers)
        return

    # --- Enrichment mode ---
    # Find cameras without launch prices
    candidates = []
    skipped_no_img = 0
    for cam in cameras:
        if cam.get("price_launch_usd"):
            continue

        if args.require_images:
            has_img = any(
                img.get("local_path") and Path(img["local_path"]).exists()
                for img in cam.get("images", [])
            )
            if not has_img:
                skipped_no_img += 1
                continue

        candidates.append(cam)

    # Prioritize cameras with year_introduced (better LLM accuracy)
    candidates.sort(key=lambda c: (0 if c.get("year_introduced") else 1, c.get("name", "")))
    to_process = candidates[: args.limit]

    print(f"Cameras without launch price: {len(candidates)}")
    if args.require_images:
        print(f"Skipped (no images): {skipped_no_img}")
    print(f"Processing: {len(to_process)}")

    if not to_process:
        print("Nothing to do.")
        return

    # Build index for fast lookup
    cam_index = {}
    for i, cam in enumerate(cameras):
        cam_index[cam.get("id", "")] = i

    enriched = 0
    unknown = 0
    failed = 0
    lock = threading.Lock()
    total = len(to_process)

    def process_one(idx_cam: tuple[int, dict]) -> tuple[int, str, dict | None]:
        i, cam = idx_cam
        name = cam["name"]
        result = _query_price(cam, client, model)
        return i, name, result

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_one, (i, cam)): i for i, cam in enumerate(to_process)}

        for future in as_completed(futures):
            i, name, result = future.result()
            cam = to_process[i]
            cam_id = cam.get("id", "")
            idx = cam_index.get(cam_id)

            with lock:
                if result and idx is not None:
                    cameras[idx]["price_launch_usd"] = result["price_usd"]
                    cameras[idx]["price_launch_currency"] = result["currency"]
                    cameras[idx]["price_launch_source"] = "llm"
                    enriched += 1
                    status = f"${result['price_usd']:.0f} ({result['currency']} {result['price']:.0f}, {result['year']})"
                elif result is None:
                    unknown += 1
                    status = "UNKNOWN"
                else:
                    failed += 1
                    status = "FAILED"

                done = enriched + unknown + failed
                print(f"  [{done}/{total}] {name}: {status}", flush=True)

                # Checkpoint every 50 enrichments
                if enriched > 0 and enriched % 50 == 0:
                    data_path.write_text(json.dumps(cameras, ensure_ascii=False, indent=2))
                    print(f"  [checkpoint: {enriched} prices saved]", flush=True)

    if enriched > 0:
        data_path.write_text(json.dumps(cameras, ensure_ascii=False, indent=2))
        print(f"\nSaved {data_path}")

    print(f"\nDone: {enriched} prices found, {unknown} unknown, {failed} failed")
    print(f"Hit rate: {enriched}/{enriched + unknown} ({enriched / max(1, enriched + unknown) * 100:.0f}%)")
    if enriched > 0:
        print("Next: uv run python scripts/enrich_prices.py  (to recalculate inflation-adjusted prices)")
        print("Then: uv run python scripts/prepare_camera_pages.py  (to regenerate frontend data)")


if __name__ == "__main__":
    main()
