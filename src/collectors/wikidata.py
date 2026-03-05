"""Collect camera and film data from Wikidata via the MediaWiki API.

Uses wbgetentities API (not SPARQL) to avoid rate limiting on the SPARQL endpoint.
Strategy:
  1. Enumerate items via category or SPARQL (with fallback)
  2. Fetch entity details in batches of 50 via wbgetentities
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from src.models.camera import Camera, Film, ImageReference, SourceReference
from src.normalization.manufacturers import get_manufacturer_country, normalize_manufacturer
from src.utils.data_io import save_records
from src.utils.http import RateLimitedClient

WD_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Camera subclass QIDs to query
CAMERA_TYPE_QIDS = {
    "Q15328": "camera",
    "Q178384": "SLR",
    "Q1144720": "TLR",
    "Q1373573": "rangefinder camera",
    "Q753159": "large format camera",
    "Q1473572": "medium format camera",
    "Q196077": "instant camera",
    "Q5375404": "box camera",
    "Q1783618": "folding camera",
    "Q1783070": "view camera",
    "Q2415988": "point-and-shoot camera",
    "Q2056764": "press camera",
    "Q1144663": "subminiature camera",
    "Q60654817": "film camera",
    "Q67541856": "camera model",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_claim_value(claims: dict, prop: str) -> str | None:
    """Extract the first value of a property from Wikidata claims."""
    if prop not in claims:
        return None
    for claim in claims[prop]:
        mainsnak = claim.get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        vtype = datavalue.get("type")
        value = datavalue.get("value")
        if vtype == "wikibase-entityid":
            return value.get("id")
        if vtype == "string":
            return value
        if vtype == "time":
            # Extract year from "+1959-01-01T00:00:00Z"
            time_str = value.get("time", "")
            if time_str:
                try:
                    return str(int(time_str[1:5]))
                except (ValueError, IndexError):
                    pass
        if vtype == "quantity":
            return value.get("amount", "").lstrip("+")
    return None


def _get_commons_url(claims: dict) -> str | None:
    """Extract image URL from P18 (image) claim."""
    if "P18" not in claims:
        return None
    for claim in claims["P18"]:
        filename = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if filename:
            # Convert filename to Commons URL
            filename = filename.replace(" ", "_")
            return f"https://commons.wikimedia.org/wiki/File:{filename}"
    return None


async def _get_qids_via_backlinks(client: RateLimitedClient, type_qid: str) -> list[str]:
    """Find items linked to a type QID using the backlinks API.

    This is more reliable than SPARQL (no rate-limit bans) and finds
    all items that reference the type QID (mostly P31 claims).
    """
    qids: list[str] = []
    params = {
        "action": "query",
        "list": "backlinks",
        "bltitle": type_qid,
        "blnamespace": "0",
        "bllimit": "500",
        "format": "json",
    }

    while True:
        resp = await client.get(WD_API, params=params)
        data = resp.json()
        for item in data.get("query", {}).get("backlinks", []):
            title = item.get("title", "")
            if title.startswith("Q"):
                qids.append(title)
        cont = data.get("continue")
        if cont and "blcontinue" in cont:
            params["blcontinue"] = cont["blcontinue"]
        else:
            break

    return qids


async def _get_qids_via_sparql(client: RateLimitedClient, type_qid: str) -> list[str]:
    """Get QIDs for instances of a type using SPARQL. Used when backlinks returns too few."""
    query = f"SELECT ?item WHERE {{ ?item wdt:P31 wd:{type_qid} . }}"
    try:
        resp = await client.get(
            SPARQL_ENDPOINT,
            params={"query": query},
            headers={"Accept": "application/sparql-results+json"},
        )
        data = resp.json()
        qids = []
        for binding in data.get("results", {}).get("bindings", []):
            uri = binding.get("item", {}).get("value", "")
            if "entity/Q" in uri:
                qids.append(uri.rsplit("/", 1)[-1])
        return qids
    except Exception as e:
        print(f"    SPARQL fallback failed for {type_qid}: {e}")
        return []


def _entity_has_p31(entity: dict, type_qid: str) -> bool:
    """Check if an entity's P31 (instance of) claim includes the given type QID."""
    claims = entity.get("claims", {})
    for claim in claims.get("P31", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if value.get("id") == type_qid:
            return True
    return False


async def _fetch_entities(client: RateLimitedClient, qids: list[str]) -> list[dict]:
    """Fetch full entity data in batches of 50."""
    entities = []
    for i in range(0, len(qids), 50):
        batch = qids[i:i + 50]
        params = {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "labels|claims",
            "languages": "en",
            "format": "json",
        }
        try:
            resp = await client.get(WD_API, params=params)
            data = resp.json()
            for qid, entity in data.get("entities", {}).items():
                if "missing" not in entity:
                    entities.append(entity)
        except Exception as e:
            print(f"    Batch fetch failed: {e}")
    return entities


async def _resolve_entity_labels(client: RateLimitedClient, qids: set[str]) -> dict[str, str]:
    """Resolve QIDs to their English labels."""
    if not qids:
        return {}
    labels = {}
    qid_list = list(qids)
    for i in range(0, len(qid_list), 50):
        batch = qid_list[i:i + 50]
        params = {
            "action": "wbgetentities",
            "ids": "|".join(batch),
            "props": "labels",
            "languages": "en",
            "format": "json",
        }
        try:
            resp = await client.get(WD_API, params=params)
            data = resp.json()
            for qid, entity in data.get("entities", {}).items():
                label = entity.get("labels", {}).get("en", {}).get("value")
                if label:
                    labels[qid] = label
        except Exception:
            pass
    return labels


def _entity_to_camera(entity: dict, manufacturer_labels: dict[str, str], camera_type: str | None = None) -> Camera | None:
    """Convert a Wikidata entity to a Camera model."""
    qid = entity.get("id")
    label = entity.get("labels", {}).get("en", {}).get("value")
    if not label:
        return None

    claims = entity.get("claims", {})

    # Manufacturer
    mfr_qid = _get_claim_value(claims, "P176")
    manufacturer_raw = manufacturer_labels.get(mfr_qid, "") if mfr_qid else "Unknown"
    manufacturer_norm = normalize_manufacturer(manufacturer_raw)

    # Year
    year_str = _get_claim_value(claims, "P571")
    year_introduced = int(year_str) if year_str and year_str.isdigit() else None

    # Image
    images: list[ImageReference] = []
    commons_url = _get_commons_url(claims)
    if commons_url:
        images.append(ImageReference(url=commons_url, source="wikidata", license="CC"))

    # Commons category
    commons_cat = _get_claim_value(claims, "P373")

    # Film format
    format_qid = _get_claim_value(claims, "P2009")
    film_format = manufacturer_labels.get(format_qid) if format_qid else None

    return Camera(
        name=label,
        manufacturer=manufacturer_raw,
        manufacturer_normalized=manufacturer_norm,
        manufacturer_country=get_manufacturer_country(manufacturer_raw),
        wikidata_qid=qid,
        camera_type=camera_type,
        film_format=film_format,
        year_introduced=year_introduced,
        images=images,
        sources=[
            SourceReference(
                source="wikidata",
                source_id=qid,
                source_url=f"https://www.wikidata.org/wiki/{qid}",
                retrieved_at=_now_iso(),
            )
        ],
        description=f"Wikimedia Commons category: {commons_cat}" if commons_cat else None,
    )


def _entity_to_film(entity: dict, manufacturer_labels: dict[str, str]) -> Film | None:
    """Convert a Wikidata entity to a Film model."""
    qid = entity.get("id")
    label = entity.get("labels", {}).get("en", {}).get("value")
    if not label:
        return None

    claims = entity.get("claims", {})

    mfr_qid = _get_claim_value(claims, "P176")
    manufacturer_raw = manufacturer_labels.get(mfr_qid, "") if mfr_qid else "Unknown"
    manufacturer_norm = normalize_manufacturer(manufacturer_raw)

    year_str = _get_claim_value(claims, "P571")
    year_introduced = int(year_str) if year_str and year_str.isdigit() else None

    iso_str = _get_claim_value(claims, "P6789")
    iso_speed = int(float(iso_str)) if iso_str else None

    images: list[ImageReference] = []
    commons_url = _get_commons_url(claims)
    if commons_url:
        images.append(ImageReference(url=commons_url, source="wikidata", license="CC"))

    return Film(
        name=label,
        manufacturer=manufacturer_raw,
        manufacturer_normalized=manufacturer_norm,
        wikidata_qid=qid,
        iso_speed=iso_speed,
        year_introduced=year_introduced,
        images=images,
        sources=[
            SourceReference(
                source="wikidata",
                source_id=qid,
                source_url=f"https://www.wikidata.org/wiki/{qid}",
                retrieved_at=_now_iso(),
            )
        ],
    )


async def _collect() -> None:
    """Main collection routine."""
    async with RateLimitedClient(min_delay=2.0, max_retries=5) as client:
        # Phase 1: Collect all camera QIDs
        print("Phase 1: Discovering camera QIDs from Wikidata...")
        all_camera_qids: dict[str, str] = {}  # QID -> camera_type

        for type_qid, type_label in CAMERA_TYPE_QIDS.items():
            print(f"  Querying {type_label} (wd:{type_qid})...", flush=True)
            qids = await _get_qids_via_backlinks(client, type_qid)
            new = 0
            for qid in qids:
                if qid not in all_camera_qids:
                    all_camera_qids[qid] = type_label
                    new += 1
            print(f"    Found {len(qids)} items ({new} new)", flush=True)

        print(f"\nTotal unique camera QIDs: {len(all_camera_qids)}")

        # Phase 1b: Film QIDs
        print("\nDiscovering film QIDs...", flush=True)
        # Q6293 = photographic film, Q1745370 = film stock (some overlap)
        film_qids = await _get_qids_via_backlinks(client, "Q6293")
        film_qids_extra = await _get_qids_via_backlinks(client, "Q1745370")
        film_qids = list(set(film_qids + film_qids_extra))
        print(f"Total unique film QIDs: {len(film_qids)}")

        # Phase 2: Fetch full entities and filter
        print("\nPhase 2: Fetching camera entities...", flush=True)
        raw_camera_entities = await _fetch_entities(client, list(all_camera_qids.keys()))
        # Filter: keep only entities that:
        #   1. Have P31 matching a camera type
        #   2. Have a manufacturer (P176) — this excludes scientific instruments and concepts
        camera_type_set = set(CAMERA_TYPE_QIDS.keys())
        camera_entities = []
        for entity in raw_camera_entities:
            claims = entity.get("claims", {})
            p31_values = {
                c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
                for c in claims.get("P31", [])
            }
            has_camera_p31 = bool(p31_values & camera_type_set)
            has_manufacturer = "P176" in claims
            if has_camera_p31 and has_manufacturer:
                camera_entities.append(entity)
        print(f"  Fetched {len(raw_camera_entities)}, kept {len(camera_entities)} (with camera P31 + manufacturer)", flush=True)

        print("Fetching film entities...", flush=True)
        raw_film_entities = await _fetch_entities(client, film_qids)
        # Filter: require P31 match AND manufacturer (P176)
        film_entities = [
            e for e in raw_film_entities
            if (_entity_has_p31(e, "Q6293") or _entity_has_p31(e, "Q1745370"))
            and "P176" in e.get("claims", {})
        ]
        print(f"  Fetched {len(raw_film_entities)}, kept {len(film_entities)} (with film P31 + manufacturer)", flush=True)

        # Phase 3: Resolve manufacturer labels
        print("\nPhase 3: Resolving manufacturer labels...")
        mfr_qids: set[str] = set()
        format_qids: set[str] = set()
        for entity in camera_entities + film_entities:
            claims = entity.get("claims", {})
            mfr = _get_claim_value(claims, "P176")
            if mfr:
                mfr_qids.add(mfr)
            fmt = _get_claim_value(claims, "P2009")
            if fmt:
                format_qids.add(fmt)

        all_labels = await _resolve_entity_labels(client, mfr_qids | format_qids)
        print(f"  Resolved {len(all_labels)} labels")

        # Phase 4: Build models
        print("\nPhase 4: Building camera models...")
        cameras: list[Camera] = []
        for entity in camera_entities:
            qid = entity.get("id")
            cam_type = all_camera_qids.get(qid)
            cam = _entity_to_camera(entity, all_labels, camera_type=cam_type)
            if cam:
                cameras.append(cam)
        print(f"  Built {len(cameras)} camera models")

        print("Building film models...")
        films: list[Film] = []
        for entity in film_entities:
            film = _entity_to_film(entity, all_labels)
            if film:
                films.append(film)
        print(f"  Built {len(films)} film models")

    # Save
    if cameras:
        save_records(cameras, source="wikidata", entity_type="cameras")
    if films:
        save_records(films, source="wikidata", entity_type="films")

    print(f"\nWikidata collection complete: {len(cameras)} cameras, {len(films)} films")


def main() -> None:
    """Entry point for the Wikidata collector."""
    asyncio.run(_collect())


if __name__ == "__main__":
    main()
