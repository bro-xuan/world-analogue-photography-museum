"""Merge and deduplicate camera/film records from all sources.

Priority order: wikidata > wikipedia > flickr
Deduplication:
  1. Wikidata QID match (definitive)
  2. Exact match on normalized (manufacturer, model_name)
  3. Fuzzy match (Levenshtein < 3) within same manufacturer
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from thefuzz import fuzz

from src.normalization.manufacturers import get_manufacturer_country, normalize_manufacturer
from src.utils.data_io import MERGED_DIR, load_records, save_merged

SOURCES_PRIORITY = ["wikidata", "wikipedia", "camerawiki", "chinesecamera", "collectiblend", "flickr"]

# ---------------------------------------------------------------------------
# Chinese manufacturer name mapping (Chinese characters -> English brand name)
# Used to prepend English name to Chinese-only camera names
# ---------------------------------------------------------------------------
CHINESE_BRAND_NAMES: dict[str, str] = {
    "海鸥": "Seagull",
    "凤凰": "Phenix",
    "珠江": "Pearl River",
    "长城": "Great Wall",
    "华夏": "Huaxia",
    "东方": "Dongfang",
    "红旗": "Red Flag",
    "红梅": "Hongmei",
    "牡丹": "Mudan",
    "孔雀": "Kongque",
    "华山": "Huashan",
    "上海": "Shanghai",
    "天津": "Tianjin",
    "太湖": "Taihu",
    "西湖": "Xihu",
    "虎丘": "Huqiu",
    "友谊": "Youyi",
    "华中": "Hua Zhong",
    "青岛": "Qingdao",
    "万灵": "Wanling",
    "三友": "Sanyou",
    "七一": "Qiyi July1st",
    "万能达": "Wannengda",
    "春雷": "Chunlei",
    "晨光": "Chenguang",
    "百花": "Baihua",
    "甘光": "Gangguang",
    "燕京": "Yanjing",
    "紫金山": "Zijinshan",
    "劳动": "Laodong",
    "幸福": "Xingfu",
    "环球": "Huanqiu",
    "神龙": "Shenlong",
    "华蓥": "Huaying",
    "明佳": "Mingjia",
    "雄鹰": "Xiongying",
    "泰": "Tai",
}


def _add_english_name(record: dict) -> None:
    """If camera name is Chinese-only, prepend English manufacturer/brand name."""
    name = record.get("name", "")
    # Check if name contains Chinese characters but no Latin letters
    if not re.search(r"[\u4e00-\u9fff]", name):
        return
    if re.search(r"[a-zA-Z]", name):
        return  # Already has English text

    # Try to map the Chinese brand prefix to English
    for cn, en in CHINESE_BRAND_NAMES.items():
        if name.startswith(cn):
            # Replace Chinese brand with English, keep the rest
            suffix = name[len(cn):].strip()
            record["name"] = f"{en} {suffix}" if suffix else en
            return

    # Fallback: prepend manufacturer_normalized
    mfr = record.get("manufacturer_normalized", "")
    if mfr:
        record["name"] = f"{mfr} {name}"


# ---------------------------------------------------------------------------
# Film format normalization
# ---------------------------------------------------------------------------
# Map messy free-text film_format values to canonical format names.
_FORMAT_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b135\b|35\s*mm|\btype\s*135\b|\bfull[- ]?frame\b', re.I), "135"),
    (re.compile(r'\b120\b|\btype\s*120\b', re.I), "120"),
    (re.compile(r'\b220\b', re.I), "220"),
    (re.compile(r'\b110\b|\bpocket\b', re.I), "110"),
    (re.compile(r'\b126\b|\binstamatic\b', re.I), "126"),
    (re.compile(r'\b127\b', re.I), "127"),
    (re.compile(r'\b8\s*[x×]\s*10\b', re.I), "8x10"),
    (re.compile(r'\b5\s*[x×]\s*7\b', re.I), "5x7"),
    (re.compile(r'\b4\s*[x×]\s*5\b', re.I), "4x5"),
    (re.compile(r'\binstant\b|\bpolaroid\b|\binstax\b|\bintegral\b|\bpack\s*film\b', re.I), "Instant"),
    (re.compile(r'\bAPS\b|\badvanced photo system\b', re.I), "APS"),
    (re.compile(r'\bdisc\b', re.I), "Disc"),
    (re.compile(r'\bhalf[- ]?frame\b', re.I), "Half-frame"),
    (re.compile(r'\bsubminiature\b|\bminox\b|\b8\s*[x×]\s*11\b|\b9\.5\s*mm\b|\b16\s*mm\b', re.I), "Subminiature"),
    (re.compile(r'\bmedium\s*format\b|\b6\s*[x×]\s*[4-9]', re.I), "120"),
    (re.compile(r'\blarge\s*format\b|\bsheet\s*film\b', re.I), "4x5"),
]

# Infer film_format from camera_type when film_format is missing
_TYPE_TO_FORMAT: dict[str, str] = {
    "SLR": "135",
    "Rangefinder": "135",
    "Point-and-shoot": "135",
    "Instant": "Instant",
    "Box camera": "120",
    "Medium format": "120",
    "View camera": "4x5",
}


def _normalize_film_format(raw: str | None) -> str | None:
    """Normalize a free-text film_format value to a canonical name."""
    if not raw:
        return None
    for pattern, canonical in _FORMAT_RULES:
        if pattern.search(raw):
            return canonical
    return raw  # Return original if no rule matches


# Name-based patterns for inferring film_format from camera name
_NAME_FORMAT_RULES: list[tuple[re.Pattern, str]] = [
    # Instant cameras
    (re.compile(r'\binstax\b|\bpolaroid\b|\binstant\b|\bsx-70\b|\bspectra\b|\boneStep\b|\bone\s*step\b|\bimpulse\b', re.I), "Instant"),
    # Medium format series
    (re.compile(r'\b6[x×]\d|rolleiflex|rolleicord|\bRB\s*67\b|\bRZ\s*67\b|\b645\b|\bbronica\b|\bmamiya\s*c\b|\bhasselblad\b|\b500\s*c\b|\b500\s*cm\b|\b503\b|\bpentax\s*6', re.I), "120"),
    # Large format
    (re.compile(r'\b4[x×]5\b|\b8[x×]10\b|\bspeed\s*graphic\b|\bcrown\s*graphic\b|\blinhof\b|\bview\s*camera\b', re.I), "4x5"),
    # 110 format
    (re.compile(r'\b110\b.*\bcamera\b|\b110\s+(?:slr|zoom|film)|pocket\s*instamatic', re.I), "110"),
    # 126 format (Instamatic)
    (re.compile(r'\binstamatic\b', re.I), "126"),
    # Subminiature
    (re.compile(r'\bminox\b|\bsubminiature\b', re.I), "Subminiature"),
    # Disc
    (re.compile(r'\bdisc\s*camera\b|\bdisc\s*\d', re.I), "Disc"),
    # Stereo cameras are mostly 35mm
    (re.compile(r'\bstereo\b', re.I), "135"),
]

# Known medium format manufacturer+model prefixes
_MEDIUM_FORMAT_PREFIXES = {
    "mamiya rb", "mamiya rz", "mamiya c", "mamiya 645",
    "bronica sq", "bronica etr", "bronica gs",
    "hasselblad 500", "hasselblad 503", "hasselblad 200", "hasselblad 2000",
    "rolleiflex", "rolleicord",
    "pentax 6", "pentax 645",
    "fuji gx", "fuji gw", "fuji ga",
}


def _infer_film_format(record: dict) -> str | None:
    """Infer film_format from camera name, type, and manufacturer."""
    name = record.get("name", "").lower()
    cam_type = record.get("camera_type", "") or ""
    mfr = (record.get("manufacturer_normalized") or "").lower()

    # 1. Check camera_type mapping
    if cam_type in _TYPE_TO_FORMAT:
        return _TYPE_TO_FORMAT[cam_type]

    # 2. Check name-based patterns
    full_name = record.get("name", "")
    for pattern, fmt in _NAME_FORMAT_RULES:
        if pattern.search(full_name):
            return fmt

    # 3. Medium format prefixes
    for prefix in _MEDIUM_FORMAT_PREFIXES:
        if name.startswith(prefix):
            return "120"

    # 4. Manufacturer-based defaults
    # Polaroid → Instant
    if mfr == "polaroid":
        return "Instant"
    # Minox → Subminiature
    if mfr == "minox":
        return "Subminiature"
    # Graflex / Linhof → Large format
    if mfr in ("graflex", "linhof"):
        return "4x5"
    # Bronica, Hasselblad, Mamiya → Medium format (if not already matched)
    if mfr in ("bronica", "hasselblad"):
        return "120"

    # 5. Most remaining analogue cameras from major Japanese/German brands are 35mm
    major_35mm_brands = {
        "nikon", "canon", "minolta", "olympus", "pentax", "yashica",
        "contax", "leica", "voigtlander", "praktica", "exakta",
        "ricoh", "chinon", "cosina", "petri", "miranda", "topcon",
        "fed", "zorki", "zenit", "kiev", "lomo", "smena",
        "argus", "kodak", "fujifilm", "konica", "agfa",
        "rollei", "zeiss ikon", "balda", "wirgin", "bell & howell",
        "coronet", "houghton", "keystone", "berning robot", "ica",
        "alpa", "revere", "riken", "ansco", "ernemann", "goerz",
        "phenix", "huaxia", "xing fu", "nanjing", "changjiang",
        "huashan", "zi jin shan",
    }
    if mfr in major_35mm_brands:
        return "135"

    return None

# Fields where we prefer non-None values from higher-priority sources
CAMERA_MERGE_FIELDS = [
    "camera_type", "film_format", "year_introduced", "year_discontinued",
    "launch_date", "lens_mount", "shutter_speed_range", "metering", "weight_g",
    "dimensions", "battery", "description", "manufacturer_country",
    "price_launch_usd", "price_adjusted_usd", "price_market_usd",
]
FILM_MERGE_FIELDS = [
    "film_type", "iso_speed", "available_formats", "is_current",
    "year_introduced", "year_discontinued", "launch_date",
    "grain", "color_rendition", "description",
]

# Keywords that indicate a non-retail/non-consumer camera (military, scientific, space, etc.)
_NON_RETAIL_KEYWORDS = [
    "satellite", "spacecraft", "space station", "orbital", "mars rover",
    "hubble", "europa imaging", "james webb", "faint object",
    "advanced camera for surveys", "high resolution camera",
    "orbiter", "chandra",
    "military", "army", "navy", "air force", "missile", "torpedo",
    "helicopter", "eurocopter", "tiger", "apache", "osprey", "osiris",
    "surveillance", "reconnaissance", "spy", "FLIR", "thermal imaging",
    "x-ray", "x ray", "medical imaging", "endoscope", "microscope",
    "industrial inspection", "borescope",
    "traffic camera", "speed camera", "dashcam", "dash cam",
    "security camera", "CCTV", "body cam", "bodycam",
    "drone camera", "UAV",
    "red epic", "red one", "red scarlet", "cinema camera",
]
_NON_RETAIL_PATTERNS = [re.compile(r'\b' + re.escape(kw) + r'\b', re.I) for kw in _NON_RETAIL_KEYWORDS]

# Novelty/branded toy cameras (not serious photography tools)
_NOVELTY_PATTERNS = [
    re.compile(r"\bbugs\s+bunny\b", re.I),
    re.compile(r"\bcrayola\b", re.I),
    re.compile(r"\bbarbie\b", re.I),
    re.compile(r"\bsnoopy\b", re.I),
    re.compile(r"\bpokemon\b|\bpokémon\b", re.I),
    re.compile(r"\bsesame\s+street\b", re.I),
    re.compile(r"\bspider-?man\b", re.I),
    re.compile(r"\bstar\s+wars\b", re.I),
    re.compile(r"\bdisney\b", re.I),
    re.compile(r"\bnickelodeon\b", re.I),
    re.compile(r"\btoy\s+story\b", re.I),
    re.compile(r"\bhello\s+kitty\b", re.I),
    re.compile(r"\bmickey\s+mouse\b", re.I),
]

# Manufacturers that are not consumer camera companies
_NON_RETAIL_MANUFACTURERS = {
    "ball aerospace & technologies", "dornier", "smithsonian astrophysical observatory",
    "space applications centre", "sagem", "general electric",
    "red digital cinema camera company", "nintendo",
}

# Wiki category/descriptor names that got parsed as manufacturer names
_WIKI_NOISE_MANUFACTURERS = {
    "slr", "compact camera", "hot shoe", "view camera", "toy camera",
    "digital camera", "fixed focus", "instant camera", "rangefinder camera",
    "viewfinder camera", "point and shoot", "pc socket", "35mm", "red window",
    "companies such as", "chinese manufacturer", "template:chinese",
    "\"35mm", "\"olympia\"",
}

# Collectiblend "manufacturers" that are actually country/aggregate categories
_COLLECTIBLEND_COUNTRY_CATEGORIES = {
    "all", "great britain", "france", "germany", "japan", "united states",
    "argentina", "australia", "austria", "belarus", "belgium", "brasil",
    "bulgaria", "canada", "china", "czech republic", "denmark", "finland",
    "hong kong", "hungary", "india", "italy", "ireland", "latvia",
    "liechtenstein", "monaco", "morocco", "mexico", "netherlands",
    "new zealand", "poland", "romania", "russia", "singapore", "slovakia",
    "south korea", "spain", "sweden", "switzerland", "taiwan", "ukraine",
    "uruguay",
}

# Patterns for digital cameras (not analogue)
_DIGITAL_PATTERNS = [
    re.compile(r"\bdigital\b", re.I),
    re.compile(r"\bDSLR\b", re.I),
    re.compile(r"\bmirrorless\b", re.I),
    re.compile(r"\bEOS\s*\d+D\b", re.I),
    re.compile(r"\bEOS\s*R\d", re.I),
    re.compile(r"\bEOS\s*M\d", re.I),
    re.compile(r"\bEOS\s*C\d", re.I),  # Canon Cinema EOS
    re.compile(r"\bD-SLR\b", re.I),
    re.compile(r"\bPowerShot\b", re.I),
    re.compile(r"\bCoolPix\b", re.I),
    re.compile(r"\bCyber-shot\b", re.I),
    re.compile(r"\bLumix\b", re.I),
    re.compile(r"\bNEX-", re.I),
    re.compile(r"\bILCE-", re.I),
    re.compile(r"\bSLT-", re.I),
    re.compile(r"\bGoPro\b", re.I),
    re.compile(r"\biPhone\b", re.I),
    re.compile(r"\bGalaxy\s*Camera\b", re.I),
    re.compile(r"\bDSC-[A-Z]\d", re.I),
    re.compile(r"\bDMC-", re.I),
    re.compile(r"\bDC-", re.I),
    re.compile(r"\bOM-D\b", re.I),
    re.compile(r"\bGFX\b", re.I),
    re.compile(r"\bwebcam\b", re.I),
    re.compile(r"\bDashCam\b", re.I),
    re.compile(r"\bExilim\b", re.I),
    re.compile(r"\bOptio\b", re.I),
    re.compile(r"\bPixii\b", re.I),
    # Olympus digital compacts
    re.compile(r"\bOlympus\s+C-\d{3,4}\b", re.I),
    re.compile(r"\bCamedia\b", re.I),
    # Leica digital series (but NOT the 1973 film Leica CL)
    re.compile(r"\bLeica\s+X[\s-]", re.I),
    re.compile(r"\bLeica\s+X$", re.I),
    re.compile(r"\bLeica\s+Q\d*\b", re.I),
    re.compile(r"\bLeica\s+SL\d*\b", re.I),
    re.compile(r"\bLeica\s+TL\d*\b", re.I),
    # Nikon digital
    re.compile(r"\bNikon\s+1\s+", re.I),
    re.compile(r"\bNikon\s+Z\d", re.I),
    re.compile(r"\bNikon\s+Zf\b", re.I),
    re.compile(r"\bNikon\s+ZR\b", re.I),
    # Other digital compacts/series
    re.compile(r"\bFinePix\s+[FZJ]\d", re.I),
    re.compile(r"\bPentax\s+Q\b", re.I),
    re.compile(r"\bSamsung\s+NX", re.I),
    re.compile(r"\bSony\s+[αa]\d{4}\b", re.I),
    re.compile(r"\bPanasonic\s+AG-", re.I),
    # Fujifilm digital
    re.compile(r"\bFinePix\b", re.I),
    re.compile(r"\bFujifilm\s+X-[A-Z]\d", re.I),  # X-S1, X-T1, X-E1, etc.
    re.compile(r"\bFujifilm\s+X\d{2,}", re.I),  # X20, X100, etc.
    re.compile(r"\bFujifilm\s+DX-", re.I),
    re.compile(r"\bFujifilm\s+XF\d", re.I),
    # Leica digital
    re.compile(r"\bDigilux\b", re.I),
    re.compile(r"\bD-Lux\b", re.I),
    re.compile(r"\bV-Lux\b", re.I),
    # Olympus digital
    re.compile(r"\bOlympus\s+FE-", re.I),
    re.compile(r"\bOlympus\s+VR-", re.I),
    re.compile(r"\bOlympus\s+VH-", re.I),
    re.compile(r"\bOlympus\s+SZ-", re.I),
    re.compile(r"\bOlympus\s+SP-", re.I),
    re.compile(r"\bOlympus\s+SH-", re.I),
    re.compile(r"\bOlympus\s+TG-", re.I),
    re.compile(r"\bOlympus\s+E-\d{3,}", re.I),  # E-300, E-500, etc.
    re.compile(r"\bOlympus\s+PEN\s+E-", re.I),  # PEN E-PL series
    re.compile(r"\bTough\s+TG-", re.I),
    re.compile(r"\bOM\s+System\b", re.I),
    # HP/other digital compacts
    re.compile(r"\bPhotosmart\b", re.I),
    re.compile(r"\bPhotoSmart\b", re.I),
    re.compile(r"\bEasyShare\b", re.I),
    # Sony digital
    re.compile(r"\bSony\s+RX\d", re.I),
    re.compile(r"\bSony\s+ZV-", re.I),
    # Ricoh digital
    re.compile(r"\bRicoh\s+GR\b", re.I),  # GR digital
    re.compile(r"\bRicoh\s+GXR\b", re.I),
    re.compile(r"\bRicoh\s+WG-", re.I),
    re.compile(r"\bRicoh\s+G\d{3}", re.I),  # G700, G900
    re.compile(r"\bRicoh\s+Caplio\b", re.I),
    re.compile(r"\bPentax\s+\*?ist\b", re.I),  # Pentax *ist series (DSLR)
    re.compile(r"\bPentax\s+K-[1-9]\d?\b", re.I),  # Pentax K-1, K-3, K-5, K-7 (DSLR, not K1000)
    re.compile(r"\bK\d{2,3}D\b", re.I),  # K10D, K20D, K100D, K200D
    re.compile(r"\bPentax\s+KP\b", re.I),
    re.compile(r"\bPentax\s+KF\b", re.I),
    re.compile(r"\bPentax\s+K-S\d", re.I),  # K-S1, K-S2
    re.compile(r"\bPentax\s+K-r\b", re.I),
    # Samsung digital
    re.compile(r"\bDigimax\b", re.I),
    # Olympus digital compacts
    re.compile(r"\bStylus\s+SH\b", re.I),
    re.compile(r"\bOlympus\s+Stylus\s+1\b", re.I),  # Stylus 1 (digital compact)
    re.compile(r"\bOlympus\s+Stylus\s+Tough\b", re.I),
    # Camcorders
    re.compile(r"\bHandycam\b", re.I),
    re.compile(r"\bHF\s+[SRM]\d", re.I),  # Canon HF series
    re.compile(r"\bcamcorder\b", re.I),
    # Pentax digital
    re.compile(r"\bPentax\s+MX-1\b", re.I),
    # camera_type indicators
    re.compile(r"Still image camera with motion capability", re.I),
]

# Specific camera names/models that are digital (not caught by patterns)
_DIGITAL_NAMES = {
    "olympus air", "sigma fp", "zeiss zx1", "epson r-d1", "red epic",
    "leica x1", "leica m8", "leica m9", "leica m10", "leica m11",
    "leica m (typ 240)", "leica m (typ 262)", "leica m monochrom",
    "leica m monochrom (typ 246)", "leica m-d (typ 262)", "leica m-e",
    "leica m-e (typ 240)", "leica m10 monochrom", "leica m10-d",
    "pentax x-5", "pentax x90", "pentax xg-1",
    "rollei qz cameras", "samsung galaxy camera", "samsung galaxy camera 2",
    "hello kitty pocket camera",
    # Leica CL digital (2017+) — NOT the 1973 film Leica CL
    "leica cl 'betriebskamera'",
    # Olympus digital compacts with alphanumeric suffixes not caught by C-\d{3,4}
    "olympus c-730uz",
}


def _is_non_retail(record: dict) -> bool:
    """Check if a camera record represents a non-retail/non-consumer product."""
    name = record.get("name", "")
    desc = record.get("description", "") or ""
    text = f"{name} {desc}"
    for pat in _NON_RETAIL_PATTERNS:
        if pat.search(text):
            return True
    for pat in _NOVELTY_PATTERNS:
        if pat.search(text):
            return True
    mfr = (record.get("manufacturer_normalized") or record.get("manufacturer", "")).lower()
    if mfr in _NON_RETAIL_MANUFACTURERS:
        return True
    if mfr in _COLLECTIBLEND_COUNTRY_CATEGORIES:
        return True
    if mfr in _WIKI_NOISE_MANUFACTURERS:
        return True
    return False


# Manufacturers that only made digital cameras (never analogue)
_DIGITAL_ONLY_MANUFACTURERS = {
    "hewlett packard", "hp",
    "benq", "acer", "dell", "gateway", "mustek",
    "om system",
}


def _is_digital(record: dict) -> bool:
    """Check if a camera is digital (not analogue)."""
    name = record.get("name", "")
    if name.lower() in _DIGITAL_NAMES:
        return True
    mfr = (record.get("manufacturer_normalized") or record.get("manufacturer", "")).lower()
    if mfr in _DIGITAL_ONLY_MANUFACTURERS:
        return True
    cam_type = record.get("camera_type", "") or ""
    text = f"{name} {cam_type}"
    for pat in _DIGITAL_PATTERNS:
        if pat.search(text):
            return True
    return False


def _normalize_name(name: str) -> str:
    """Normalize a camera/film name for matching."""
    s = name.lower().strip()
    # Remove common suffixes/prefixes that vary between sources
    s = re.sub(r'\s+', ' ', s)
    # Remove trademark symbols
    s = s.replace('™', '').replace('®', '').replace('©', '')
    return s


def _make_key(manufacturer: str, name: str) -> str:
    """Create a dedup key from manufacturer + name."""
    mfr = normalize_manufacturer(manufacturer).lower().strip()
    n = _normalize_name(name)
    return f"{mfr}|{n}"


def _merge_record(base: dict, overlay: dict, fields: list[str]) -> dict:
    """Merge overlay into base, preferring non-None overlay values."""
    merged = dict(base)
    for field in fields:
        overlay_val = overlay.get(field)
        if overlay_val is not None and overlay_val != "" and overlay_val != []:
            if merged.get(field) is None or merged.get(field) == "" or merged.get(field) == []:
                merged[field] = overlay_val
    # Merge images (combine, deduplicate by URL)
    base_images = {img["url"]: img for img in merged.get("images", [])}
    for img in overlay.get("images", []):
        if img["url"] not in base_images:
            base_images[img["url"]] = img
    merged["images"] = list(base_images.values())
    # Merge sources
    merged_sources = list(merged.get("sources", []))
    for src in overlay.get("sources", []):
        if not any(s.get("source") == src.get("source") and s.get("source_id") == src.get("source_id") for s in merged_sources):
            merged_sources.append(src)
    merged["sources"] = merged_sources
    # Take QIDs if available
    if overlay.get("wikidata_qid") and not merged.get("wikidata_qid"):
        merged["wikidata_qid"] = overlay["wikidata_qid"]
    if overlay.get("flickr_id") and not merged.get("flickr_id"):
        merged["flickr_id"] = overlay["flickr_id"]
    return merged


def _merge_entities(all_records: list[dict], merge_fields: list[str]) -> tuple[list[dict], dict]:
    """Merge and deduplicate a list of entity records.

    Returns (merged_records, stats_dict).
    """
    # Index by QID and by normalized key
    by_qid: dict[str, dict] = {}
    by_key: dict[str, dict] = {}
    fuzzy_candidates: dict[str, list[dict]] = {}  # manufacturer -> [records]
    review_queue: list[dict] = []
    stats = {"total_input": len(all_records), "qid_matches": 0, "exact_matches": 0, "fuzzy_matches": 0}

    for record in all_records:
        # Normalize manufacturer
        mfr = record.get("manufacturer", "")
        record["manufacturer_normalized"] = normalize_manufacturer(mfr)

        qid = record.get("wikidata_qid")
        key = _make_key(record.get("manufacturer", ""), record.get("name", ""))

        # 1. QID match
        if qid and qid in by_qid:
            by_qid[qid] = _merge_record(by_qid[qid], record, merge_fields)
            # Also update key index to point to same record
            by_key[key] = by_qid[qid]
            stats["qid_matches"] += 1
            continue

        # 2. Exact key match
        if key in by_key:
            existing = by_key[key]
            merged = _merge_record(existing, record, merge_fields)
            by_key[key] = merged
            if qid:
                by_qid[qid] = merged
            elif existing.get("wikidata_qid"):
                by_qid[existing["wikidata_qid"]] = merged
            stats["exact_matches"] += 1
            continue

        # New record — store it
        if qid:
            by_qid[qid] = record
        by_key[key] = record

        # Track for fuzzy matching
        mfr_norm = record["manufacturer_normalized"].lower()
        fuzzy_candidates.setdefault(mfr_norm, []).append(record)

    # 3. Fuzzy matching pass within same manufacturer
    merged_keys = set()
    for mfr, candidates in fuzzy_candidates.items():
        names = [(c, _normalize_name(c.get("name", ""))) for c in candidates]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                rec_i, name_i = names[i]
                rec_j, name_j = names[j]
                key_i = _make_key(rec_i.get("manufacturer", ""), rec_i.get("name", ""))
                key_j = _make_key(rec_j.get("manufacturer", ""), rec_j.get("name", ""))
                if key_i == key_j:
                    continue  # Already exact-matched
                pair_key = tuple(sorted([key_i, key_j]))
                if pair_key in merged_keys:
                    continue
                ratio = fuzz.ratio(name_i, name_j)
                if ratio >= 90 and len(name_i) > 3 and len(name_j) > 3:
                    # Skip if either key was already merged away
                    if key_i not in by_key or key_j not in by_key:
                        merged_keys.add(pair_key)
                        continue
                    # Merge j into i (keep the one from higher-priority source)
                    src_i = (rec_i.get("sources") or [{}])[0].get("source", "")
                    src_j = (rec_j.get("sources") or [{}])[0].get("source", "")
                    pri_i = SOURCES_PRIORITY.index(src_i) if src_i in SOURCES_PRIORITY else 99
                    pri_j = SOURCES_PRIORITY.index(src_j) if src_j in SOURCES_PRIORITY else 99
                    if pri_i <= pri_j:
                        by_key[key_i] = _merge_record(by_key[key_i], by_key[key_j], merge_fields)
                        del by_key[key_j]
                    else:
                        by_key[key_j] = _merge_record(by_key[key_j], by_key[key_i], merge_fields)
                        del by_key[key_i]
                    merged_keys.add(pair_key)
                    stats["fuzzy_matches"] += 1
                elif 80 <= ratio < 90 and len(name_i) > 3:
                    review_queue.append({
                        "name_a": rec_i.get("name"),
                        "name_b": rec_j.get("name"),
                        "manufacturer": mfr,
                        "similarity": ratio,
                    })

    # Assign UUIDs, add English names for Chinese cameras, populate launch_date
    results = []
    for record in by_key.values():
        record["id"] = str(uuid.uuid4())
        _add_english_name(record)
        if not record.get("launch_date") and record.get("year_introduced"):
            record["launch_date"] = str(record["year_introduced"])
        if not record.get("manufacturer_country"):
            mfr = record.get("manufacturer_normalized") or record.get("manufacturer", "")
            country = get_manufacturer_country(mfr)
            if country:
                record["manufacturer_country"] = country
        # Normalize film_format, then infer from name/type/manufacturer if still missing
        record["film_format"] = _normalize_film_format(record.get("film_format"))
        if not record.get("film_format"):
            record["film_format"] = _infer_film_format(record)
        results.append(record)

    stats["total_output"] = len(results)
    stats["dedup_rate"] = round((1 - len(results) / max(stats["total_input"], 1)) * 100, 1)
    stats["review_queue_size"] = len(review_queue)

    # Save review queue
    if review_queue:
        review_path = MERGED_DIR / "review_queue.json"
        MERGED_DIR.mkdir(parents=True, exist_ok=True)
        review_path.write_text(json.dumps(review_queue, indent=2, ensure_ascii=False))
        print(f"  Saved {len(review_queue)} fuzzy-match candidates to {review_path}")

    return results, stats


def merge_cameras() -> tuple[list[dict], dict]:
    """Load and merge camera records from all sources."""
    all_records = []
    for source in SOURCES_PRIORITY:
        records = load_records(source, "cameras")
        print(f"  Loaded {len(records)} cameras from {source}")
        all_records.extend(records)
    merged, stats = _merge_entities(all_records, CAMERA_MERGE_FIELDS)
    # Filter out non-retail cameras (military, scientific, surveillance, etc.)
    before = len(merged)
    merged = [r for r in merged if not _is_non_retail(r)]
    non_retail_count = before - len(merged)
    # Filter out digital cameras (this is an analogue photography museum)
    before2 = len(merged)
    merged = [r for r in merged if not _is_digital(r)]
    digital_count = before2 - len(merged)
    total_filtered = non_retail_count + digital_count
    if total_filtered:
        print(f"  Filtered {non_retail_count} non-retail + {digital_count} digital cameras")
        stats["non_retail_filtered"] = non_retail_count
        stats["digital_filtered"] = digital_count
        stats["total_output"] = len(merged)
    return merged, stats


def merge_films() -> tuple[list[dict], dict]:
    """Load and merge film records from all sources."""
    all_records = []
    for source in SOURCES_PRIORITY:
        records = load_records(source, "films")
        print(f"  Loaded {len(records)} films from {source}")
        all_records.extend(records)
    return _merge_entities(all_records, FILM_MERGE_FIELDS)


def main():
    print("=" * 60)
    print("MERGING CAMERA DATA")
    print("=" * 60)
    cameras, cam_stats = merge_cameras()
    save_merged([c for c in cameras], "cameras")

    print()
    print("=" * 60)
    print("MERGING FILM DATA")
    print("=" * 60)
    films, film_stats = merge_films()
    save_merged([f for f in films], "films")

    print()
    print("=" * 60)
    print("MERGE SUMMARY")
    print("=" * 60)
    print(f"Cameras: {cam_stats['total_input']} input -> {cam_stats['total_output']} merged "
          f"({cam_stats['dedup_rate']}% dedup rate)")
    print(f"  QID matches: {cam_stats['qid_matches']}, "
          f"Exact matches: {cam_stats['exact_matches']}, "
          f"Fuzzy matches: {cam_stats['fuzzy_matches']}")
    print(f"  Review queue: {cam_stats['review_queue_size']} candidates")
    print()
    print(f"Films: {film_stats['total_input']} input -> {film_stats['total_output']} merged "
          f"({film_stats['dedup_rate']}% dedup rate)")
    print(f"  QID matches: {film_stats['qid_matches']}, "
          f"Exact matches: {film_stats['exact_matches']}, "
          f"Fuzzy matches: {film_stats['fuzzy_matches']}")
    print(f"  Review queue: {film_stats['review_queue_size']} candidates")


if __name__ == "__main__":
    main()
