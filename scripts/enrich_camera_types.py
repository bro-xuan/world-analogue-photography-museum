#!/usr/bin/env python3
"""Enrich camera types using batched LLM inference.

Classifies cameras into canonical types: SLR, TLR, Rangefinder, Point & Shoot,
Folding, Box, View, Instant, Panoramic, Stereo, Toy, Medium Format, Bridge,
Subminiature, Mirrorless.

Usage:
    ZAI_API_KEY=xxx uv run python scripts/enrich_camera_types.py --limit 10500 --workers 3
    ZAI_API_KEY=xxx uv run python scripts/enrich_camera_types.py --validate --limit 300 --workers 3
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TYPES = {
    "SLR", "TLR", "Rangefinder", "Point & Shoot", "Folding", "Box", "View",
    "Instant", "Panoramic", "Stereo", "Toy", "Medium Format", "Bridge",
    "Subminiature", "Mirrorless",
}

# Garbage values that should be overwritten
GARBAGE_TYPES = {
    "camera", "35 mm", "35mm", "film camera", "digital camera", "unknown",
    "other", "compact", "compact camera", "", "none",
}

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

BATCH_PROMPT = """\
Classify each camera into exactly ONE type from this list:
SLR, TLR, Rangefinder, Point & Shoot, Folding, Box, View, Instant, Panoramic, Stereo, Toy, Medium Format, Bridge, Subminiature, Mirrorless

Rules:
- Medium format SLR → SLR (not Medium Format)
- Medium format TLR → TLR (not Medium Format)
- Medium format rangefinder → Rangefinder (not Medium Format)
- "Medium Format" is only for cameras that don't fit the above (e.g., medium format folders → Folding)
- Compact autofocus cameras → Point & Shoot
- Half-frame cameras → classify by their viewfinder type (SLR, Rangefinder, etc.)
- Disposable/single-use → Point & Shoot
- If truly unknown, respond UNKNOWN for that camera

Respond with ONLY a JSON array:
[{{"id": "...", "type": "..."}}, ...]

Cameras:
"""


def _build_batch_text(batch: list[dict]) -> str:
    """Build the camera list to append to the prompt."""
    lines = []
    for cam in batch:
        name = cam["name"]
        mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
        fmt = cam.get("film_format") or ""
        year = cam.get("year_introduced") or ""
        desc = (cam.get("description") or "")[:150].replace("\n", " ")
        cam_id = cam.get("id", "")[:8]
        lines.append(f'- id="{cam_id}" | {mfr} {name} | format={fmt} | year={year} | {desc}')
    return "\n".join(lines)


def _parse_batch_response(text: str, batch: list[dict]) -> dict[str, str]:
    """Parse LLM JSON array response into {short_id: type} dict."""
    text = text.strip()

    # Find JSON array in response
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        return {}

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, list):
        return {}

    result = {}
    valid_lower = {t.lower(): t for t in VALID_TYPES}
    for item in data:
        if not isinstance(item, dict):
            continue
        cam_id = str(item.get("id", ""))
        cam_type = str(item.get("type", ""))
        if not cam_id or not cam_type:
            continue
        # Normalize the type
        normalized = valid_lower.get(cam_type.lower().strip())
        if normalized:
            result[cam_id] = normalized

    return result


def _query_batch(
    batch: list[dict],
    client: OpenAI,
    model: str,
) -> dict[str, str]:
    """Ask LLM to classify a batch of cameras. Returns {short_id: type}."""
    prompt = BATCH_PROMPT + _build_batch_text(batch)

    for attempt in range(5):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.1,
            )
            text = (resp.choices[0].message.content or "").strip()
            if not text:
                # Empty response — retry with backoff
                time.sleep((attempt + 1) * 3)
                continue
            return _parse_batch_response(text, batch)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower():
                wait = (attempt + 1) * 10
                time.sleep(wait)
                continue
            if attempt == 4:
                return {}
            time.sleep(3)
    return {}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _run_validation(
    cameras: list[dict],
    client: OpenAI,
    model: str,
    limit: int,
    workers: int,
    batch_size: int,
) -> None:
    """Compare LLM classifications against existing camera_type values."""
    # Find cameras with existing non-garbage types
    classified = []
    for cam in cameras:
        raw = (cam.get("camera_type") or "").strip()
        if not raw or raw.lower() in GARBAGE_TYPES:
            continue
        classified.append(cam)

    print(f"Found {len(classified)} cameras with existing types")
    if limit > 0:
        classified = classified[:limit]
    print(f"Validating {len(classified)}...")

    # Build batches
    batches = [classified[i:i + batch_size] for i in range(0, len(classified), batch_size)]

    matches = 0
    misses = 0
    unknowns = 0
    total = len(classified)
    lock = threading.Lock()
    done_count = 0

    # Build expected map from existing normalize logic
    from scripts.prepare_camera_pages import _normalize_camera_type

    def validate_batch(batch: list[dict]) -> list[tuple[str, str, str | None]]:
        results_map = _query_batch(batch, client, model)
        out = []
        for cam in batch:
            cam_id = cam.get("id", "")[:8]
            name = cam["name"]
            expected = _normalize_camera_type(cam.get("camera_type"))
            llm_type = results_map.get(cam_id)
            out.append((name, expected or cam.get("camera_type", ""), llm_type))
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(validate_batch, b): i for i, b in enumerate(batches)}

        for future in as_completed(futures):
            results = future.result()
            with lock:
                for name, expected, llm_type in results:
                    done_count += 1
                    if llm_type is None:
                        unknowns += 1
                        status = f"UNKNOWN (expected={expected})"
                    elif llm_type == expected:
                        matches += 1
                        status = f"MATCH ({llm_type})"
                    else:
                        misses += 1
                        status = f"MISS (LLM={llm_type} vs expected={expected})"
                    print(f"  [{done_count}/{total}] {name}: {status}", flush=True)

    answered = matches + misses
    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"Total tested:    {total}")
    print(f"UNKNOWN:         {unknowns} ({unknowns * 100 // max(1, total)}%)")
    print(f"Answered:        {answered} ({answered * 100 // max(1, total)}%)")
    if answered > 0:
        accuracy = matches * 100 // answered
        print(f"  Correct:       {matches} ({accuracy}% of answered)")
        print(f"  Wrong:         {misses} ({misses * 100 // answered}% of answered)")
        print(f"\nAccuracy: {accuracy}%")
        if accuracy >= 90:
            print("=> EXCELLENT: Types are highly reliable")
        elif accuracy >= 80:
            print("=> GOOD: Types are reliable enough for direct use")
        else:
            print("=> NEEDS REVIEW: Consider manual spot-checking")


# ---------------------------------------------------------------------------
# Main enrichment
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Enrich camera types via batched LLM")
    parser.add_argument("--limit", type=int, default=100, help="Max cameras to process")
    parser.add_argument("--model", default=None, help="LLM model name")
    parser.add_argument("--api-base", default=None, help="Custom OpenAI-compatible API base URL")
    parser.add_argument("--api-key", default=None, help="Custom API key")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent LLM requests")
    parser.add_argument("--batch-size", type=int, default=10, help="Cameras per LLM call")
    parser.add_argument("--validate", action="store_true", help="Compare LLM vs existing types")
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
        _run_validation(cameras, client, model, args.limit, args.workers, args.batch_size)
        return

    # --- Enrichment mode ---
    # Find cameras needing type classification
    candidates = []
    skipped_no_img = 0
    already_typed = 0
    for cam in cameras:
        existing = (cam.get("camera_type") or "").strip().lower()
        if existing and existing not in GARBAGE_TYPES:
            already_typed += 1
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

    # Prioritize cameras with images on disk first, then by name
    def _sort_key(c: dict) -> tuple[int, str]:
        has_img = any(
            img.get("local_path") and Path(img["local_path"]).exists()
            for img in c.get("images", [])
        )
        return (0 if has_img else 1, c.get("name", ""))

    candidates.sort(key=_sort_key)
    to_process = candidates[:args.limit]

    print(f"Already typed: {already_typed}")
    print(f"Cameras needing type: {len(candidates)}")
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

    # Build batches
    batches = [to_process[i:i + args.batch_size] for i in range(0, len(to_process), args.batch_size)]

    enriched = 0
    unknown = 0
    lock = threading.Lock()
    total = len(to_process)

    def process_batch(batch_idx_batch: tuple[int, list[dict]]) -> tuple[int, dict[str, str]]:
        batch_idx, batch = batch_idx_batch
        results = _query_batch(batch, client, model)
        return batch_idx, results

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(process_batch, (i, batch)): i
            for i, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            batch_idx, results = future.result()
            batch = batches[batch_idx]

            with lock:
                for cam in batch:
                    cam_id = cam.get("id", "")
                    short_id = cam_id[:8]
                    idx = cam_index.get(cam_id)
                    name = cam["name"]

                    llm_type = results.get(short_id)
                    if llm_type and idx is not None:
                        cameras[idx]["camera_type"] = llm_type
                        enriched += 1
                        status = llm_type
                    else:
                        unknown += 1
                        status = "UNKNOWN"

                    done = enriched + unknown
                    print(f"  [{done}/{total}] {name}: {status}", flush=True)

                # Checkpoint every 100 enrichments
                if enriched > 0 and enriched % 100 < args.batch_size:
                    data_path.write_text(json.dumps(cameras, ensure_ascii=False, indent=2))
                    print(f"  [checkpoint: {enriched} types saved]", flush=True)

    if enriched > 0:
        data_path.write_text(json.dumps(cameras, ensure_ascii=False, indent=2))
        print(f"\nSaved {data_path}")

    print(f"\nDone: {enriched} types classified, {unknown} unknown")
    print(f"Hit rate: {enriched}/{total} ({enriched * 100 // max(1, total)}%)")
    if enriched > 0:
        print("Next: uv run python scripts/prepare_camera_pages.py  (to regenerate frontend data)")


if __name__ == "__main__":
    main()
