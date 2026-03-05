"""Collect camera and film data from Wikipedia via the MediaWiki API."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from src.models.camera import Camera, Film, SourceReference
from src.normalization.manufacturers import get_manufacturer_country, normalize_manufacturer
from src.utils.data_io import save_records
from src.utils.http import RateLimitedClient

API_URL = "https://en.wikipedia.org/w/api.php"
ARTICLE_BASE = "https://en.wikipedia.org/wiki/"

CAMERA_CATEGORIES = [
    "Category:Film cameras",
    "Category:Cameras by brand",
    "Category:35mm SLR cameras",
    "Category:Medium format cameras",
    "Category:Instant cameras",
    "Category:Rangefinder cameras",
    "Category:Box cameras",
    "Category:Folding cameras",
    "Category:Toy cameras",
    "Category:Chinese cameras",
    "Category:Japanese cameras",
    "Category:German cameras",
    "Category:Soviet cameras",
    "Category:Twin-lens reflex cameras",
    "Category:Subminiature cameras",
    "Category:Press cameras",
    "Category:View cameras",
    "Category:Stereo cameras",
    "Category:Panoramic cameras",
    "Category:Underwater cameras",
    "Category:Large format cameras",
    "Category:APS film cameras",
    "Category:Disc cameras",
    "Category:Pinhole cameras",
]

FILM_CATEGORIES = [
    "Category:Photographic films",
]

CAMERA_LIST_PAGES = [
    "List of Canon products",
    "List of Nikon products",
    "List of Minolta products",
    "List of Olympus products",
    "List of Pentax products",
    "List of Contax products",
    "List of Yashica products",
    "List of Mamiya products",
    "List of Hasselblad products",
    "List of Leica products",
    "List of Rollei products",
    "List of Ricoh products",
    "List of Kodak products",
    "List of Polaroid products",
    "List of Fujifilm cameras",
    "List of Voigtländer products",
    "List of Agfa cameras",
    "List of Konica products",
    "List of Bronica products",
    "List of Praktica cameras",
]

FILM_LIST_PAGES = [
    "List of photographic films",
    "Photographic film",
]


# ---------------------------------------------------------------------------
# Wikitext cleaning helpers
# ---------------------------------------------------------------------------

def _clean_wikitext(value: str) -> str:
    """Strip common wikitext markup from a value string."""
    if not value:
        return value
    text = value

    # {{nowrap|...}} -> content
    text = re.sub(r'\{\{nowrap\|([^}]*)\}\}', r'\1', text, flags=re.IGNORECASE)
    # {{convert|...|...|...}} -> first number + unit
    text = re.sub(r'\{\{convert\|([^|]+)\|([^|}]+)[^}]*\}\}', r'\1 \2', text, flags=re.IGNORECASE)
    # Other templates: {{...}} -> empty (remove remaining templates)
    text = re.sub(r'\{\{[^}]*\}\}', '', text)

    # [[Target|Display text]] -> Display text
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', text)

    # Clean up residual ]] or [[ from partial wikilinks
    text = text.replace(']]', '').replace('[[', '')

    # Remove bold/italic markup
    text = text.replace("'''", "").replace("''", "")

    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # HTML entities
    text = text.replace('&nbsp;', ' ').replace('&ndash;', '-').replace('&mdash;', '-')

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _parse_year(value: str) -> tuple[int | None, int | None]:
    """Extract year_introduced and year_discontinued from a string like '1959' or '1959-1975'."""
    if not value:
        return None, None
    cleaned = _clean_wikitext(value)
    # Range: "1959-1975", "1959 - 1975", "1959–1975"
    m = re.search(r'(\d{4})\s*[-–]\s*(\d{4})', cleaned)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Single year
    m = re.search(r'(\d{4})', cleaned)
    if m:
        return int(m.group(1)), None
    return None, None


# ---------------------------------------------------------------------------
# Infobox parsing
# ---------------------------------------------------------------------------

def _extract_infobox(wikitext: str, template_names: list[str]) -> dict[str, str]:
    """Extract key-value pairs from an infobox template in wikitext.

    Handles nested braces by counting brace depth.
    """
    # Find the start of the infobox
    pattern = r'\{\{\s*(' + '|'.join(re.escape(n) for n in template_names) + r')\s*\n?\|'
    match = re.search(pattern, wikitext, re.IGNORECASE)
    if not match:
        return {}

    start = match.start()
    # Walk forward counting braces to find the matching close
    depth = 0
    i = start
    end = len(wikitext)
    while i < end:
        if wikitext[i:i+2] == '{{':
            depth += 1
            i += 2
        elif wikitext[i:i+2] == '}}':
            depth -= 1
            if depth == 0:
                i += 2
                break
            i += 2
        else:
            i += 1

    infobox_text = wikitext[start:i]

    # Split on top-level pipes (depth == 1 relative to this infobox)
    params: dict[str, str] = {}
    current_key = None
    current_value_parts: list[str] = []
    depth = 0

    for char_idx in range(len(infobox_text)):
        c = infobox_text[char_idx:char_idx+2]
        if c == '{{':
            depth += 1
        elif c == '}}':
            depth -= 1

    # Simpler approach: split the infobox body (skip the header line) on "\n|"
    # which is how MediaWiki infobox params are typically separated
    body = infobox_text[match.end() - start:]  # after the first |
    # Split on newline-pipe at the top level
    lines = re.split(r'\n\s*\|', body)
    for line in lines:
        if '=' in line:
            key, _, val = line.partition('=')
            key = key.strip().lower()
            val = val.strip()
            # Remove trailing }} that might be the infobox close
            val = re.sub(r'\}\}\s*$', '', val).strip()
            if key and not key.startswith('{'):
                params[key] = val

    return params


# ---------------------------------------------------------------------------
# Wikitable parsing
# ---------------------------------------------------------------------------

def _parse_wikitables(wikitext: str) -> list[list[dict[str, str]]]:
    """Parse wikitables from wikitext. Returns a list of tables, each a list of row-dicts."""
    tables: list[list[dict[str, str]]] = []
    # Find table blocks
    table_pattern = re.compile(r'\{\|.*?\|\}', re.DOTALL)
    for table_match in table_pattern.finditer(wikitext):
        table_text = table_match.group()
        headers: list[str] = []
        rows: list[dict[str, str]] = []

        lines = table_text.split('\n')
        current_row: list[str] = []
        in_header = False

        for line in lines:
            line = line.strip()
            if line.startswith('!'):
                # Header cells
                in_header = True
                cells = re.split(r'!!', line[1:])
                for cell in cells:
                    # Remove formatting before the last |
                    if '|' in cell and not cell.strip().startswith('[['):
                        cell = cell.rsplit('|', 1)[-1]
                    headers.append(_clean_wikitext(cell.strip()))
            elif line.startswith('|-'):
                # Row separator
                if current_row and headers:
                    row_dict = {}
                    for idx, val in enumerate(current_row):
                        if idx < len(headers):
                            row_dict[headers[idx]] = _clean_wikitext(val)
                    rows.append(row_dict)
                current_row = []
                in_header = False
            elif line.startswith('|') and not line.startswith('|}') and not line.startswith('{|'):
                # Data cells
                cells = re.split(r'\|\|', line[1:])
                for cell in cells:
                    if '|' in cell and not cell.strip().startswith('[['):
                        cell = cell.rsplit('|', 1)[-1]
                    current_row.append(cell.strip())

        # Last row
        if current_row and headers:
            row_dict = {}
            for idx, val in enumerate(current_row):
                if idx < len(headers):
                    row_dict[headers[idx]] = _clean_wikitext(val)
            rows.append(row_dict)

        if rows:
            tables.append(rows)

    return tables


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

async def _get_category_members(
    client: RateLimitedClient,
    category: str,
    cmtype: str = "page",
) -> list[dict]:
    """Enumerate all members of a Wikipedia category, handling pagination."""
    members: list[dict] = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmlimit": "500",
        "cmtype": cmtype,
        "format": "json",
    }

    while True:
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        batch = data.get("query", {}).get("categorymembers", [])
        members.extend(batch)
        cont = data.get("continue")
        if cont and "cmcontinue" in cont:
            params["cmcontinue"] = cont["cmcontinue"]
        else:
            break

    return members


async def _get_wikitext(client: RateLimitedClient, title: str) -> str | None:
    """Fetch the wikitext of a Wikipedia article."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
    }
    try:
        resp = await client.get(API_URL, params=params)
        data = resp.json()
        return data.get("parse", {}).get("wikitext", {}).get("*")
    except Exception as e:
        print(f"  Failed to fetch wikitext for '{title}': {e}")
        return None


def _article_url(title: str) -> str:
    return ARTICLE_BASE + title.replace(" ", "_")


# ---------------------------------------------------------------------------
# Camera extraction
# ---------------------------------------------------------------------------

_CAMERA_INFOBOX_NAMES = [
    "Infobox camera",
    "Infobox Camera",
    "Infobox camera model",
]

_CAMERA_TYPE_MAP = {
    "slr": "SLR",
    "single-lens reflex": "SLR",
    "single lens reflex": "SLR",
    "tlr": "TLR",
    "twin-lens reflex": "TLR",
    "rangefinder": "Rangefinder",
    "point-and-shoot": "Point-and-shoot",
    "point and shoot": "Point-and-shoot",
    "compact": "Point-and-shoot",
    "view camera": "View camera",
    "large format": "View camera",
    "medium format": "Medium format",
    "instant": "Instant",
    "box camera": "Box camera",
    "folding": "Folding",
}


def _normalize_camera_type(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = _clean_wikitext(raw).lower()
    for key, val in _CAMERA_TYPE_MAP.items():
        if key in cleaned:
            return val
    return _clean_wikitext(raw)


def _camera_from_infobox(title: str, params: dict[str, str]) -> Camera | None:
    """Build a Camera from infobox parameters."""
    name = _clean_wikitext(params.get("name", "")) or title
    manufacturer_raw = _clean_wikitext(
        params.get("manufacturer", "")
        or params.get("maker", "")
        or params.get("brand", "")
    )
    if not manufacturer_raw:
        # Try to infer from title: "Nikon F3" -> "Nikon"
        parts = title.split()
        if len(parts) >= 2:
            manufacturer_raw = parts[0]
        else:
            manufacturer_raw = ""

    if not manufacturer_raw:
        return None

    year_intro, year_disc = _parse_year(
        params.get("produced", "")
        or params.get("intro_year", "")
        or params.get("year", "")
        or params.get("production", "")
    )

    film_format = _clean_wikitext(
        params.get("film_format", "")
        or params.get("film_size", "")
        or params.get("format", "")
    ) or None

    camera_type = _normalize_camera_type(
        params.get("type", "")
        or params.get("camera_type", "")
    )

    lens_mount = _clean_wikitext(params.get("lens_mount", "") or params.get("mount", "")) or None
    shutter = _clean_wikitext(params.get("shutter", "") or params.get("shutter_speeds", "")) or None
    metering = _clean_wikitext(params.get("metering", "") or params.get("meter", "")) or None
    weight_raw = _clean_wikitext(params.get("weight", ""))
    weight_g = None
    if weight_raw:
        m = re.search(r'(\d+)\s*g', weight_raw)
        if m:
            weight_g = int(m.group(1))

    now_iso = datetime.now(timezone.utc).isoformat()
    manufacturer_norm = normalize_manufacturer(manufacturer_raw)

    return Camera(
        name=name,
        manufacturer=manufacturer_raw,
        manufacturer_normalized=manufacturer_norm,
        manufacturer_country=get_manufacturer_country(manufacturer_raw),
        camera_type=camera_type,
        film_format=film_format,
        year_introduced=year_intro,
        year_discontinued=year_disc,
        lens_mount=lens_mount,
        shutter_speed_range=shutter,
        metering=metering,
        weight_g=weight_g,
        sources=[
            SourceReference(
                source="wikipedia",
                source_url=_article_url(title),
                retrieved_at=now_iso,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Film extraction
# ---------------------------------------------------------------------------

_FILM_INFOBOX_NAMES = [
    "Infobox film stock",
    "Infobox Film Stock",
    "Infobox photographic film",
]


def _film_from_infobox(title: str, params: dict[str, str]) -> Film | None:
    """Build a Film from infobox parameters."""
    name = _clean_wikitext(params.get("name", "")) or title
    manufacturer_raw = _clean_wikitext(
        params.get("manufacturer", "")
        or params.get("maker", "")
        or params.get("brand", "")
    )
    if not manufacturer_raw:
        parts = title.split()
        if len(parts) >= 2:
            manufacturer_raw = parts[0]
        else:
            return None

    year_intro, year_disc = _parse_year(
        params.get("produced", "")
        or params.get("intro_year", "")
        or params.get("year", "")
    )

    iso_raw = _clean_wikitext(params.get("iso", "") or params.get("speed", ""))
    iso_speed = None
    if iso_raw:
        m = re.search(r'(\d+)', iso_raw)
        if m:
            iso_speed = int(m.group(1))

    film_type = _clean_wikitext(params.get("type", "") or params.get("film_type", "")) or None
    grain = _clean_wikitext(params.get("grain", "")) or None

    formats_raw = _clean_wikitext(params.get("available_formats", "") or params.get("formats", ""))
    available_formats: list[str] = []
    if formats_raw:
        available_formats = [f.strip() for f in re.split(r'[,;]', formats_raw) if f.strip()]

    now_iso = datetime.now(timezone.utc).isoformat()
    manufacturer_norm = normalize_manufacturer(manufacturer_raw)

    return Film(
        name=name,
        manufacturer=manufacturer_raw,
        manufacturer_normalized=manufacturer_norm,
        film_type=film_type,
        iso_speed=iso_speed,
        available_formats=available_formats,
        year_introduced=year_intro,
        year_discontinued=year_disc,
        grain=grain,
        sources=[
            SourceReference(
                source="wikipedia",
                source_url=_article_url(title),
                retrieved_at=now_iso,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Collection routines
# ---------------------------------------------------------------------------

async def _get_all_pages_recursive(
    client: RateLimitedClient,
    category: str,
    max_depth: int = 3,
    visited: set[str] | None = None,
) -> list[dict]:
    """Recursively enumerate all pages in a category tree up to max_depth."""
    if visited is None:
        visited = set()
    if category in visited or max_depth <= 0:
        return []
    visited.add(category)
    pages = await _get_category_members(client, category, cmtype="page")
    subcats = await _get_category_members(client, category, cmtype="subcat")
    for subcat in subcats:
        sub_pages = await _get_all_pages_recursive(
            client, subcat["title"], max_depth - 1, visited
        )
        pages.extend(sub_pages)
    return pages


async def _collect_cameras_from_categories(client: RateLimitedClient) -> list[Camera]:
    """Enumerate camera categories and extract camera data from article infoboxes."""
    cameras: list[Camera] = []
    seen_titles: set[str] = set()
    visited_cats: set[str] = set()

    for top_cat in CAMERA_CATEGORIES:
        print(f"Recursively enumerating {top_cat} (depth 3)...")
        pages = await _get_all_pages_recursive(
            client, top_cat, max_depth=3, visited=visited_cats
        )
        # Deduplicate pages by title
        unique_pages = []
        for page in pages:
            if page["title"] not in seen_titles:
                unique_pages.append(page)
                seen_titles.add(page["title"])
        print(f"  Found {len(unique_pages)} unique pages")

        for page in unique_pages:
            title = page["title"]
            wikitext = await _get_wikitext(client, title)
            if not wikitext:
                continue

            params = _extract_infobox(wikitext, _CAMERA_INFOBOX_NAMES)
            if not params:
                continue

            camera = _camera_from_infobox(title, params)
            if camera:
                cameras.append(camera)
                print(f"    + {camera.name} ({camera.manufacturer})")

    return cameras


async def _collect_cameras_from_lists(client: RateLimitedClient) -> list[Camera]:
    """Parse list articles for camera data from wikitables."""
    cameras: list[Camera] = []

    for page_title in CAMERA_LIST_PAGES:
        print(f"Parsing list page: {page_title}...")
        wikitext = await _get_wikitext(client, page_title)
        if not wikitext:
            continue

        tables = _parse_wikitables(wikitext)
        for table in tables:
            for row in table:
                # Try to find a camera name and relevant data
                name = (
                    row.get("Model")
                    or row.get("Name")
                    or row.get("Camera")
                    or row.get("Product")
                )
                if not name:
                    continue
                name = _clean_wikitext(name)
                if not name or len(name) < 2:
                    continue

                # Infer manufacturer from page title
                manufacturer_raw = page_title.replace("List of ", "").replace(" products", "").strip()
                year_raw = row.get("Year") or row.get("Introduced") or row.get("Date") or ""
                year_intro, year_disc = _parse_year(year_raw)

                cam_type = _normalize_camera_type(row.get("Type", ""))
                film_format = _clean_wikitext(row.get("Film format", "") or row.get("Format", "")) or None
                lens_mount = _clean_wikitext(row.get("Lens mount", "") or row.get("Mount", "")) or None

                now_iso = datetime.now(timezone.utc).isoformat()
                manufacturer_norm = normalize_manufacturer(manufacturer_raw)

                camera = Camera(
                    name=name,
                    manufacturer=manufacturer_raw,
                    manufacturer_normalized=manufacturer_norm,
                    manufacturer_country=get_manufacturer_country(manufacturer_raw),
                    camera_type=cam_type,
                    film_format=film_format,
                    year_introduced=year_intro,
                    year_discontinued=year_disc,
                    lens_mount=lens_mount,
                    sources=[
                        SourceReference(
                            source="wikipedia",
                            source_url=_article_url(page_title),
                            retrieved_at=now_iso,
                        )
                    ],
                )
                cameras.append(camera)
                print(f"    + {camera.name} ({camera.manufacturer})")

    return cameras


async def _collect_films_from_categories(client: RateLimitedClient) -> list[Film]:
    """Enumerate film categories and extract film data from article infoboxes."""
    films: list[Film] = []
    seen_titles: set[str] = set()

    for cat in FILM_CATEGORIES:
        print(f"Enumerating {cat}...")
        # Get direct pages
        pages = await _get_category_members(client, cat, cmtype="page")
        # Also get subcategories and their pages
        subcats = await _get_category_members(client, cat, cmtype="subcat")
        print(f"  Found {len(pages)} pages and {len(subcats)} subcategories")

        for subcat in subcats:
            sub_pages = await _get_category_members(client, subcat["title"], cmtype="page")
            pages.extend(sub_pages)
            print(f"  {subcat['title']}: {len(sub_pages)} pages")

        for page in pages:
            title = page["title"]
            if title in seen_titles:
                continue
            seen_titles.add(title)

            wikitext = await _get_wikitext(client, title)
            if not wikitext:
                continue

            params = _extract_infobox(wikitext, _FILM_INFOBOX_NAMES)
            if not params:
                continue

            film = _film_from_infobox(title, params)
            if film:
                films.append(film)
                print(f"    + {film.name} ({film.manufacturer})")

    return films


def _parse_wikitables_with_sections(wikitext: str) -> list[tuple[str, list[dict[str, str]]]]:
    """Parse wikitext, returning (section_header, table_rows) pairs.

    Tracks the current section header (== Manufacturer ==) so we know
    which manufacturer each table belongs to.
    """
    results: list[tuple[str, list[dict[str, str]]]] = []
    current_section = ""
    lines = wikitext.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Track section headers (== or ===)
        m = re.match(r'^={2,4}\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]\s*={2,4}', line)
        if not m:
            m = re.match(r'^={2,4}\s*([^=]+?)\s*={2,4}', line)
        if m:
            current_section = _clean_wikitext(m.group(1))
            i += 1
            continue

        # Detect table start
        if line.startswith('{|'):
            # Collect table text until |}
            table_lines = [line]
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('|}'):
                table_lines.append(lines[i])
                i += 1
            if i < len(lines):
                table_lines.append(lines[i])
            table_text = "\n".join(table_lines)
            # Parse this single table
            tables = _parse_wikitables(table_text)
            for table in tables:
                if table:
                    results.append((current_section, table))

        i += 1

    return results


async def _collect_films_from_lists(client: RateLimitedClient) -> list[Film]:
    """Parse film list articles for film data from wikitables.

    The "List of photographic films" page groups films by manufacturer
    in sections (== Manufacturer ==), with tables under each section.
    """
    films: list[Film] = []

    for page_title in FILM_LIST_PAGES:
        print(f"Parsing film list page: {page_title}...")
        wikitext = await _get_wikitext(client, page_title)
        if not wikitext:
            continue

        section_tables = _parse_wikitables_with_sections(wikitext)

        for section_name, table in section_tables:
            for row in table:
                name = (
                    row.get("Film")
                    or row.get("Name")
                    or row.get("Product")
                )
                if not name:
                    continue
                name = _clean_wikitext(name)
                if not name or len(name) < 2:
                    continue

                # Try explicit manufacturer column first
                manufacturer_raw = _clean_wikitext(
                    row.get("Manufacturer", "")
                    or row.get("Company", "")
                    or row.get("Maker", "")
                )
                # Fall back to section header (the manufacturer grouping)
                if not manufacturer_raw and section_name:
                    manufacturer_raw = section_name
                # Last resort: infer from name
                if not manufacturer_raw:
                    parts = name.split()
                    if len(parts) >= 2:
                        manufacturer_raw = parts[0]
                    else:
                        continue

                iso_raw = row.get("ISO") or row.get("Speed") or row.get("ISO speed") or ""
                iso_speed = None
                if iso_raw:
                    m_iso = re.search(r'(\d+)', _clean_wikitext(iso_raw))
                    if m_iso:
                        iso_speed = int(m_iso.group(1))

                film_type = _clean_wikitext(row.get("Type", "") or row.get("Process", "")) or None
                formats_raw = row.get("Formats") or row.get("Available formats") or ""
                available_formats: list[str] = []
                if formats_raw:
                    available_formats = [f.strip() for f in re.split(r'[,;]', _clean_wikitext(formats_raw)) if f.strip()]

                now_iso = datetime.now(timezone.utc).isoformat()
                manufacturer_norm = normalize_manufacturer(manufacturer_raw)

                film = Film(
                    name=name,
                    manufacturer=manufacturer_raw,
                    manufacturer_normalized=manufacturer_norm,
                    film_type=film_type,
                    iso_speed=iso_speed,
                    available_formats=available_formats,
                    sources=[
                        SourceReference(
                            source="wikipedia",
                            source_url=_article_url(page_title),
                            retrieved_at=now_iso,
                        )
                    ],
                )
                films.append(film)
                print(f"    + {film.name} ({film.manufacturer})")

    return films


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def _collect() -> None:
    """Run all Wikipedia collection tasks."""
    async with RateLimitedClient(min_delay=1.0) as client:
        # Collect cameras
        print("=" * 60)
        print("COLLECTING CAMERAS FROM WIKIPEDIA")
        print("=" * 60)

        cat_cameras = await _collect_cameras_from_categories(client)
        list_cameras = await _collect_cameras_from_lists(client)

        # Deduplicate by name (case-insensitive)
        seen: set[str] = set()
        all_cameras: list[Camera] = []
        for cam in cat_cameras + list_cameras:
            key = cam.name.lower()
            if key not in seen:
                seen.add(key)
                all_cameras.append(cam)

        print(f"\nTotal unique cameras: {len(all_cameras)}")
        save_records(all_cameras, "wikipedia", "cameras")

        # Collect films
        print("\n" + "=" * 60)
        print("COLLECTING FILMS FROM WIKIPEDIA")
        print("=" * 60)

        cat_films = await _collect_films_from_categories(client)
        list_films = await _collect_films_from_lists(client)

        seen_films: set[str] = set()
        all_films: list[Film] = []
        for film in cat_films + list_films:
            key = film.name.lower()
            if key not in seen_films:
                seen_films.add(key)
                all_films.append(film)

        print(f"\nTotal unique films: {len(all_films)}")
        save_records(all_films, "wikipedia", "films")

        print("\nWikipedia collection complete.")


def main() -> None:
    """Entry point for the Wikipedia collector."""
    asyncio.run(_collect())


if __name__ == "__main__":
    main()
