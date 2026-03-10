#!/usr/bin/env python3
"""Enrich camera descriptions using web search + LLM summarization.

Optimized for throughput:
  - Single LLM call per camera (description + ratings combined)
  - Concurrent processing with ThreadPoolExecutor (--workers N)
  - Incremental saves every N cameras

Search providers (tried in order):
  1. Brave Search API  — if BRAVE_API_KEY env var is set (free tier: 2000/month)
  2. DuckDuckGo HTML   — no key needed, rate-limits after ~5 queries

LLM providers (any OpenAI-compatible API):
  - Z.ai GLM Coding Plan: ZAI_API_KEY (glm-4.7, glm-4.5-air)
  - OpenAI: OPENAI_API_KEY
  - Any other: --api-base + --api-key flags

Usage:
    ZAI_API_KEY=xxx uv run python scripts/enrich_descriptions_web.py --limit 500 --workers 8
    OPENAI_API_KEY=xxx uv run python scripts/enrich_descriptions_web.py --limit 1000 --workers 20
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
# Search helpers
# ---------------------------------------------------------------------------

_BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")


def _build_query(name: str, manufacturer: str, suffix: str = "camera history review") -> str:
    if manufacturer and name.lower().startswith(manufacturer.lower()):
        return f"{name} {suffix}"
    return f"{manufacturer} {name} {suffix}"


def _brave_search(query: str, max_results: int = 5) -> list[dict]:
    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": _BRAVE_API_KEY,
            },
            timeout=15,
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"title": item.get("title", ""), "body": item.get("description", "")}
            for item in data.get("web", {}).get("results", [])[:max_results]
        ]
    except Exception:
        return []


def _ddg_html_search(query: str, max_results: int = 5) -> list[dict]:
    from bs4 import BeautifulSoup

    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=15,
            verify=False,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        for item in soup.select(".result__body"):
            title_el = item.select_one(".result__title")
            snippet_el = item.select_one(".result__snippet")
            if not title_el:
                continue
            results.append({
                "title": title_el.get_text(strip=True),
                "body": snippet_el.get_text(strip=True) if snippet_el else "",
            })
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


def web_search(query: str, max_results: int = 5) -> list[dict]:
    if _BRAVE_API_KEY:
        results = _brave_search(query, max_results)
        if results:
            return results
    return _ddg_html_search(query, max_results)


# ---------------------------------------------------------------------------
# Combined prompt (description + ratings in one call)
# ---------------------------------------------------------------------------

COMBINED_PROMPT = """\
You are writing for a camera museum catalog. Your task has two parts.

**Camera:** {name} by {manufacturer}
**Year:** {year_range}
**Type:** {camera_type} | **Format:** {film_format}
**Existing info:** {existing_description}

{search_section}

## Part 1: Description
Write a description proportional to the camera's actual importance:
- Iconic/historically significant cameras (e.g. Leica M3, Nikon F, Polaroid SX-70): 2-3 rich paragraphs covering history, design, innovations, famous users.
- Notable but not legendary cameras: 1-2 solid paragraphs covering key features and context.
- Ordinary consumer/budget cameras with little historical significance: 1 concise paragraph covering what it is, when it was made, and its basic character.

Match the depth to the camera's real-world significance. Do not inflate mundane cameras with flowery language or stretch thin material. A simple camera deserves a simple, honest description. Be factual and encyclopedic. Do not invent facts. Start directly with text, no heading.

## Part 2: Ratings
Rate this camera on 4 dimensions (1.0-5.0, one decimal):
- buildQuality: physical construction, materials, durability
- value: worth for the price (launch and current market)
- collectibility: collector desirability today
- historicalSignificance: importance in photography history

After the description, output a line containing ONLY this JSON (no markdown fences):
RATINGS:{{"buildQuality":X.X,"value":X.X,"collectibility":X.X,"historicalSignificance":X.X}}"""


def _parse_response(text: str) -> tuple[str, dict | None]:
    """Split combined response into description and ratings."""
    # Find RATINGS: marker
    match = re.search(r'RATINGS:\s*(\{[^}]+\})', text)
    if match:
        desc = text[:match.start()].strip()
        try:
            ratings = json.loads(match.group(1))
            for key in ["buildQuality", "value", "collectibility", "historicalSignificance"]:
                if key in ratings:
                    ratings[key] = round(max(1.0, min(5.0, float(ratings[key]))), 1)
                else:
                    ratings = None
                    break
        except (json.JSONDecodeError, ValueError):
            ratings = None
    else:
        # Try to find JSON at end of response
        json_match = re.search(r'\{[^{}]*"buildQuality"[^{}]*\}', text)
        if json_match:
            desc = text[:json_match.start()].strip()
            try:
                ratings = json.loads(json_match.group())
                for key in ["buildQuality", "value", "collectibility", "historicalSignificance"]:
                    ratings[key] = round(max(1.0, min(5.0, float(ratings[key]))), 1)
            except Exception:
                desc = text.strip()
                ratings = None
        else:
            desc = text.strip()
            ratings = None

    # Clean up description — remove any trailing "RATINGS:" or JSON artifacts
    desc = re.sub(r'\n*RATINGS:.*$', '', desc, flags=re.DOTALL).strip()
    # Remove markdown code fences if the model wrapped the ratings
    desc = re.sub(r'\n*```json\s*\{.*$', '', desc, flags=re.DOTALL).strip()
    desc = re.sub(r'\n*```\s*$', '', desc).strip()

    return desc, ratings


def _enrich_one(
    cam: dict,
    client: OpenAI,
    model: str,
    do_search: bool,
    search_delay: float,
) -> tuple[str | None, dict | None]:
    """Enrich a single camera. Returns (description, ratings) or (None, None)."""
    name = cam["name"]
    manufacturer = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
    existing = (cam.get("description") or "").strip()

    year_intro = cam.get("year_introduced")
    year_disc = cam.get("year_discontinued")
    if year_intro and year_disc:
        year_range = f"{year_intro}–{year_disc}"
    elif year_intro:
        year_range = str(year_intro)
    else:
        year_range = "Unknown"

    camera_type = cam.get("camera_type") or "Unknown"
    film_format = cam.get("film_format") or "Unknown"

    # --- Optional web search ---
    search_section = ""
    if do_search:
        query = _build_query(name, manufacturer)
        time.sleep(search_delay)
        results = web_search(query, max_results=5)
        if results:
            lines = [f"- {r['title']}: {r['body']}" for r in results if r.get("title")]
            search_section = "**Web research:**\n" + "\n".join(lines)

    if not search_section:
        search_section = "(No web research available. Use existing info and your knowledge.)"

    prompt = COMBINED_PROMPT.format(
        name=name,
        manufacturer=manufacturer,
        existing_description=existing or "(none)",
        year_range=year_range,
        camera_type=camera_type,
        film_format=film_format,
        search_section=search_section,
    )

    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
                temperature=0.7,
            )
            text = resp.choices[0].message.content.strip()
            if not text:
                return None, None
            return _parse_response(text)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower():
                wait = (attempt + 1) * 10  # 10s, 20s, 30s
                time.sleep(wait)
                continue
            print(f"  LLM failed for {name}: {e}", flush=True)
            return None, None
    print(f"  LLM rate-limited after retries for {name}", flush=True)
    return None, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _priority_score(cam: dict) -> tuple[int, int, str]:
    has_wiki = 0
    for src in cam.get("sources", []):
        if src.get("source") in ("wikidata", "wikipedia"):
            has_wiki = 1
            break
    year = cam.get("year_introduced") or 9999
    name = cam.get("name", "")
    return (-has_wiki, year, name)


def main():
    parser = argparse.ArgumentParser(description="Enrich camera descriptions via web search + LLM")
    parser.add_argument("--limit", type=int, default=10, help="Max cameras to process")
    parser.add_argument("--min-desc", type=int, default=300, help="Skip cameras with descriptions longer than this")
    parser.add_argument("--model", default=None, help="LLM model name (auto-detected if not set)")
    parser.add_argument("--api-base", default=None, help="Custom OpenAI-compatible API base URL")
    parser.add_argument("--api-key", default=None, help="Custom API key (overrides env vars)")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent LLM requests")
    parser.add_argument("--no-search", action="store_true", help="Skip web search, use LLM knowledge only")
    parser.add_argument("--search-delay", type=float, default=0.5, help="Seconds between searches")
    parser.add_argument("--dry-run", action="store_true", help="Search only, don't call LLM")
    parser.add_argument("--require-images", action="store_true", help="Skip cameras without images on disk")
    args = parser.parse_args()

    data_path = Path("data/merged/cameras.json")
    if not data_path.exists():
        print(f"ERROR: {data_path} not found")
        sys.exit(1)

    cameras = json.loads(data_path.read_text())
    print(f"Loaded {len(cameras)} cameras")

    # Filter to cameras needing enrichment
    candidates = []
    skipped_no_img = 0
    for cam in cameras:
        if args.require_images:
            has_img = any(
                img.get("local_path") and Path(img["local_path"]).exists()
                for img in cam.get("images", [])
            )
            if not has_img:
                skipped_no_img += 1
                continue
        desc = (cam.get("description") or "").strip()
        has_ratings = cam.get("ratings") is not None
        if len(desc) < args.min_desc or not has_ratings:
            candidates.append(cam)

    candidates.sort(key=_priority_score)
    to_process = candidates[: args.limit]

    if args.require_images:
        print(f"Skipped (no images): {skipped_no_img}")
    print(f"Candidates needing enrichment: {len(candidates)}")
    print(f"Processing: {len(to_process)}")

    if not to_process:
        print("Nothing to do.")
        return

    if args.dry_run:
        print("\n--- DRY RUN: testing search only ---")
        for cam in to_process[:5]:
            name = cam["name"]
            mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
            query = _build_query(name, mfr)
            print(f"\nSearching: {query}")
            results = web_search(query, max_results=3)
            for r in results:
                print(f"  - {r.get('title', '')[:80]}")
            time.sleep(args.search_delay)
        return

    # --- Initialize LLM client ---
    api_key = args.api_key
    api_base = args.api_base
    model = args.model

    zai_key = os.environ.get("ZAI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if api_key and api_base:
        model = model or "gpt-4o-mini"
        print(f"LLM provider: custom ({api_base}, model={model})")
    elif zai_key:
        api_key = zai_key
        api_base = "https://api.z.ai/api/coding/paas/v4/"
        model = model or "glm-4.5-air"
        print(f"LLM provider: Z.ai GLM Coding Plan (model={model})")
    elif openai_key:
        api_key = openai_key
        api_base = None
        model = model or "gpt-4o-mini"
        print(f"LLM provider: OpenAI (model={model})")
    else:
        print("ERROR: No LLM API key found. Set one of:")
        print("  ZAI_API_KEY   — for Z.ai GLM Coding Plan")
        print("  OPENAI_API_KEY — for OpenAI")
        print("  --api-key + --api-base — for any OpenAI-compatible API")
        sys.exit(1)

    client_kwargs: dict = {"api_key": api_key}
    if api_base:
        client_kwargs["base_url"] = api_base
    client = OpenAI(
        **client_kwargs,
        http_client=httpx.Client(verify=False, timeout=90),
        timeout=90,
    )

    do_search = not args.no_search
    if not do_search:
        print("Web search: DISABLED (--no-search)")
    elif _BRAVE_API_KEY:
        print("Search provider: Brave Search API")
    else:
        print("Search provider: DuckDuckGo HTML")

    print(f"Workers: {args.workers}")

    # Build index for fast lookup
    cam_index = {}
    for i, cam in enumerate(cameras):
        cam_index[cam.get("id", "")] = i

    # --- Concurrent processing ---
    enriched = 0
    failed = 0
    lock = threading.Lock()
    total = len(to_process)

    def process_camera(idx_cam: tuple[int, dict]) -> tuple[int, str, str | None, dict | None]:
        i, cam = idx_cam
        name = cam["name"]
        mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
        desc, ratings = _enrich_one(cam, client, model, do_search, args.search_delay)
        return i, f"{mfr} {name}", desc, ratings

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_camera, (i, cam)): i for i, cam in enumerate(to_process)}

        for future in as_completed(futures):
            i, display_name, description, ratings = future.result()
            cam = to_process[i]
            cam_id = cam.get("id", "")
            idx = cam_index.get(cam_id)

            with lock:
                if description and idx is not None:
                    cameras[idx]["description"] = description
                    if ratings:
                        cameras[idx]["ratings"] = ratings
                    enriched += 1
                    status = f"OK: {len(description)} chars, ratings={'yes' if ratings else 'no'}"
                else:
                    failed += 1
                    status = "FAILED"

                done = enriched + failed
                print(f"  [{done}/{total}] {display_name} — {status}", flush=True)

                # Save every 20 enrichments
                if enriched > 0 and enriched % 20 == 0:
                    data_path.write_text(json.dumps(cameras, ensure_ascii=False, indent=2))
                    print(f"  [checkpoint saved: {enriched} enriched]", flush=True)

    # Final save
    if enriched > 0:
        data_path.write_text(json.dumps(cameras, ensure_ascii=False, indent=2))
        print(f"\nSaved {data_path}")

    print(f"\nDone: {enriched} enriched, {failed} failed out of {total} processed")
    if enriched > 0:
        print("Run: uv run python scripts/prepare_camera_pages.py  to regenerate detail JSON")


if __name__ == "__main__":
    main()
