"""Fetch recent eBay sold prices for cameras by scraping search results with Scrapling."""

from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.parse

from bs4 import BeautifulSoup
from scrapling import StealthyFetcher

from src.utils.data_io import MERGED_DIR

# Delay between requests — eBay challenges after too many rapid hits
MIN_DELAY = 5.0
# Recreate browser session every N requests to get a fresh fingerprint
SESSION_REFRESH_INTERVAL = 80
# Timeout for waiting for search results after challenge page
PAGE_TIMEOUT = 30_000  # ms

_fetcher: StealthyFetcher | None = None
_last_request_time: float = 0.0
_request_count: int = 0


def _get_fetcher(force_new: bool = False) -> StealthyFetcher:
    global _fetcher
    if _fetcher is None or force_new:
        _fetcher = StealthyFetcher()
    return _fetcher


def _rate_limit():
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < MIN_DELAY:
        time.sleep(MIN_DELAY - elapsed)
    _last_request_time = time.monotonic()


def _build_search_query(manufacturer: str, name: str) -> str:
    """Build a clean search query from manufacturer + model name."""
    if name.lower().startswith(manufacturer.lower()):
        query = name
    else:
        query = f"{manufacturer} {name}"
    query = re.sub(r"\s*\(.*?\)", "", query)
    query = unicodedata.normalize("NFKD", query)
    query = query.encode("ascii", "ignore").decode("ascii")
    query = re.sub(r"\s+", " ", query).strip()
    return query


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _title_is_relevant(title: str, query: str) -> bool:
    query_tokens = _tokenize(query)
    title_tokens = _tokenize(title)
    if not query_tokens:
        return False
    overlap = query_tokens & title_tokens
    return len(overlap) >= max(2, len(query_tokens) * 0.5)


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def _build_ebay_url(query: str) -> str:
    """Build eBay sold listings search URL."""
    encoded = urllib.parse.quote(query)
    return (
        f"https://www.ebay.com/sch/i.html"
        f"?_nkw={encoded}"
        f"&_sacat=15230"  # Film Cameras category
        f"&LH_Complete=1"  # Completed listings
        f"&LH_Sold=1"  # Sold only
        f"&_ipg=60"  # 60 results per page
    )


def _parse_price_text(text: str) -> float | None:
    """Parse a price string like '$399.99' or '$1,234.56'."""
    if " to " in text:
        text = text.split(" to ")[0]
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned:
        return None
    try:
        price = float(cleaned)
        if price < 5 or price > 50_000:
            return None
        return price
    except (ValueError, TypeError):
        return None


def _extract_sold_prices(html: str, query: str) -> float | None:
    """Parse eBay sold listings HTML and return median sold price."""
    soup = BeautifulSoup(str(html), "lxml")

    container = soup.find("div", id="srp-river-results")
    if not container:
        return None

    cards = container.find_all("li", class_=lambda c: c and "s-card" in c)
    if not cards:
        return None

    prices = []
    for card in cards:
        # Extract title
        title_div = card.find("div", class_="s-card__title")
        if not title_div:
            continue
        title_span = title_div.find(
            "span",
            class_=lambda c: c and "primary" in c and "su-styled-text" in c,
        )
        title = title_span.get_text(strip=True) if title_span else ""
        if not title or not _title_is_relevant(title, query):
            continue

        # Only confirmed sold prices (bold, not strikethrough)
        price_span = card.find("span", class_="s-card__price")
        if not price_span:
            continue
        classes = " ".join(price_span.get("class", []))
        if "strikethrough" in classes:
            continue
        if "bold" not in classes:
            continue

        price = _parse_price_text(price_span.get_text())
        if price is not None:
            prices.append(price)

    if not prices:
        return None

    return round(_median(prices), 2)


def _fetch_page(url: str) -> object | None:
    """Fetch an eBay search page, waiting for results through any challenge."""
    global _request_count
    _request_count += 1
    force_new = _request_count % SESSION_REFRESH_INTERVAL == 0

    _rate_limit()
    try:
        page = _get_fetcher(force_new=force_new).fetch(
            url,
            wait_selector="#srp-river-results",
            wait_selector_state="visible",
            timeout=PAGE_TIMEOUT,
            network_idle=True,
        )
        if page.status == 200 and "srp-river-results" in str(page.html_content):
            return page
    except Exception:
        pass

    # Retry with fresh session
    time.sleep(10)
    _rate_limit()
    try:
        page = _get_fetcher(force_new=True).fetch(
            url,
            wait_selector="#srp-river-results",
            wait_selector_state="visible",
            timeout=PAGE_TIMEOUT,
            network_idle=True,
        )
        if page.status == 200 and "srp-river-results" in str(page.html_content):
            return page
    except Exception:
        pass

    return None


def scrape_ebay_prices(
    limit: int = 0,
    force: bool = False,
) -> None:
    """Scrape eBay sold listings for cameras without market prices.

    Args:
        limit: Max cameras to process (0 = all).
        force: If True, also refresh existing collectiblend prices with eBay data.
    """
    cameras_path = MERGED_DIR / "cameras.json"
    if not cameras_path.exists():
        print("No merged cameras file found.")
        return

    cameras = json.loads(cameras_path.read_text())
    print(f"Loaded {len(cameras)} cameras", flush=True)

    targets: list[tuple[int, str, str]] = []
    for idx, cam in enumerate(cameras):
        has_price = cam.get("price_market_usd")
        if has_price and not force:
            continue
        if has_price and force and cam.get("price_market_source") == "ebay":
            continue

        mfr = cam.get("manufacturer_normalized") or cam.get("manufacturer", "")
        name = cam.get("name", "")
        if not mfr or not name:
            continue

        query = _build_search_query(mfr, name)
        if len(query) < 5:
            continue

        targets.append((idx, query, name))

    mode_label = "all (force refresh)" if force else "missing only"
    print(f"Found {len(targets)} cameras to price ({mode_label})", flush=True)
    if limit > 0:
        targets = targets[:limit]
        print(f"  Limiting to first {limit}", flush=True)

    updated = 0
    errors = 0
    skipped = 0
    consecutive_failures = 0

    for i, (idx, query, name) in enumerate(targets):
        if (i + 1) % 50 == 0:
            print(
                f"  Processing {i + 1}/{len(targets)}... "
                f"({updated} prices, {skipped} no results, {errors} errors)",
                flush=True,
            )
        if (i + 1) % 200 == 0:
            cameras_path.write_text(
                json.dumps(cameras, indent=2, ensure_ascii=False)
            )
            print(f"  Saved checkpoint at {i + 1}", flush=True)

        try:
            url = _build_ebay_url(query)
            page = _fetch_page(url)

            if page is None:
                errors += 1
                consecutive_failures += 1
                if errors <= 10:
                    print(f"  Failed to load '{query}'", flush=True)
                if consecutive_failures >= 5:
                    print(
                        "  5 consecutive failures — blocked. Stopping.",
                        flush=True,
                    )
                    break
                continue

            consecutive_failures = 0
            price = _extract_sold_prices(page.html_content, query)
            if price:
                cameras[idx]["price_market_usd"] = price
                cameras[idx]["price_market_source"] = "ebay"
                updated += 1
            else:
                skipped += 1

        except Exception as e:
            errors += 1
            consecutive_failures += 1
            if errors <= 10:
                print(f"  Exception for '{query}': {e}", flush=True)
            if consecutive_failures >= 5:
                print("  5 consecutive failures — stopping.", flush=True)
                break

    print(f"\neBay sold prices found: {updated}/{len(targets)}", flush=True)
    print(f"No results: {skipped}", flush=True)
    print(f"Errors: {errors}", flush=True)

    cameras_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"Saved to {cameras_path}", flush=True)


def main() -> None:
    import sys

    limit = 0
    force = False
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        if arg == "--force":
            force = True

    scrape_ebay_prices(limit=limit, force=force)


if __name__ == "__main__":
    main()
