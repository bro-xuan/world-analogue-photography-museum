"""Shared digital camera detection patterns.

Consolidated from merge.py, flickr.py, and collectiblend.py to provide
a single source of truth for identifying digital cameras.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Compiled regex patterns for digital camera detection
# ---------------------------------------------------------------------------

DIGITAL_PATTERNS: list[re.Pattern[str]] = [
    # Generic digital indicators
    re.compile(r"\bdigital\b", re.I),
    re.compile(r"\bDSLR\b", re.I),
    re.compile(r"\bmirrorless\b", re.I),
    re.compile(r"\bD-SLR\b", re.I),
    re.compile(r"\bwebcam\b", re.I),
    re.compile(r"\bDashCam\b", re.I),
    re.compile(r"\bcamcorder\b", re.I),
    re.compile(r"\bDrone\b", re.I),
    re.compile(r"\bAction\s*Cam", re.I),
    re.compile(r"\bIP\s*Cam", re.I),
    # Camera type indicators
    re.compile(r"Still image camera with motion capability", re.I),
    # Canon
    re.compile(r"\bEOS\s*\d+D\b", re.I),
    re.compile(r"\bEOS\s*R\d", re.I),
    re.compile(r"\bEOS\s*M\d", re.I),
    re.compile(r"\bEOS\s*C\d", re.I),  # Cinema EOS
    re.compile(r"\bEOS\s*D\d", re.I),  # EOS D30, D60
    re.compile(r"\bPowerShot\b", re.I),
    re.compile(r"\bHF\s+[SRM]\d", re.I),  # Canon HF camcorders
    # Nikon
    re.compile(r"\bCoolPix\b", re.I),
    re.compile(r"\bNikon\s+1\s+", re.I),
    re.compile(r"\bNikon\s+Z\d", re.I),
    re.compile(r"\bNikon\s+Zf\b", re.I),
    re.compile(r"\bNikon\s+ZR\b", re.I),
    re.compile(r"\bD\d{2,4}\b", re.I),  # Nikon D50, D200, D7000
    # Sony
    re.compile(r"\bCyber-shot\b", re.I),
    re.compile(r"\bDSC-[A-Z]\d", re.I),
    re.compile(r"\bNEX-", re.I),
    re.compile(r"\bILCE-", re.I),
    re.compile(r"\bSLT-", re.I),
    re.compile(r"\bSony\s+[αa]\d{1,4}\b", re.I),
    re.compile(r"\bSony\s+RX\d", re.I),
    re.compile(r"\bSony\s+ZV-", re.I),
    re.compile(r"\bAlpha\s*(?:DSLR|NEX|SLT|ILCE)\b", re.I),
    re.compile(r"\bHandycam\b", re.I),
    # Panasonic
    re.compile(r"\bLumix\b", re.I),
    re.compile(r"\bDMC-", re.I),
    re.compile(r"\bDC-", re.I),
    re.compile(r"\bPanasonic\s+AG-", re.I),
    # Olympus
    re.compile(r"\bOM-D\b", re.I),
    re.compile(r"\bOlympus\s+C-\d{3,4}\b", re.I),
    re.compile(r"\bCamedia\b", re.I),
    re.compile(r"\bOlympus\s+FE-", re.I),
    re.compile(r"\bOlympus\s+VR-", re.I),
    re.compile(r"\bOlympus\s+VH-", re.I),
    re.compile(r"\bOlympus\s+SZ-", re.I),
    re.compile(r"\bOlympus\s+SP-", re.I),
    re.compile(r"\bOlympus\s+SH-", re.I),
    re.compile(r"\bOlympus\s+TG-", re.I),
    re.compile(r"\bOlympus\s+E-\d{3,}", re.I),
    re.compile(r"\bOlympus\s+PEN\s+E-", re.I),
    re.compile(r"\bTough\s+TG-", re.I),
    re.compile(r"\bOM\s+System\b", re.I),
    re.compile(r"\bE-[PM]\d", re.I),  # Olympus E-P/E-M without brand prefix
    re.compile(r"\bStylus\s+SH\b", re.I),
    re.compile(r"\bOlympus\s+Stylus\s+1\b", re.I),
    re.compile(r"\bOlympus\s+Stylus\s+Tough\b", re.I),
    # Fujifilm
    re.compile(r"\bFinePix\b", re.I),
    re.compile(r"\bFujifilm\s+X-[A-Z]\d", re.I),
    re.compile(r"\bFujifilm\s+X\d{2,}", re.I),
    re.compile(r"\bFujifilm\s+DX-", re.I),
    re.compile(r"\bFujifilm\s+XF\d", re.I),
    re.compile(r"\bGFX\b", re.I),
    re.compile(r"\bX-[TEASMHP]\d", re.I),  # Fuji X-series without brand prefix
    # Leica digital
    re.compile(r"\bLeica\s+X[\s-]", re.I),
    re.compile(r"\bLeica\s+X$", re.I),
    re.compile(r"\bLeica\s+Q\d*\b", re.I),
    re.compile(r"\bLeica\s+SL\d*\b", re.I),
    re.compile(r"\bLeica\s+TL\d*\b", re.I),
    re.compile(r"\bDigilux\b", re.I),
    re.compile(r"\bD-Lux\b", re.I),
    re.compile(r"\bV-Lux\b", re.I),
    # Pentax digital
    re.compile(r"\bPentax\s+Q\b", re.I),
    re.compile(r"\bPentax\s+\*?ist\b", re.I),
    re.compile(r"\bPentax\s+K-[1-9]\d?\b", re.I),
    re.compile(r"\bK\d{2,3}D\b", re.I),
    re.compile(r"\bPentax\s+KP\b", re.I),
    re.compile(r"\bPentax\s+KF\b", re.I),
    re.compile(r"\bPentax\s+K-S\d", re.I),
    re.compile(r"\bPentax\s+K-r\b", re.I),
    re.compile(r"\bPentax\s+MX-1\b", re.I),
    re.compile(r"\bOptio\b", re.I),
    # Samsung
    re.compile(r"\bSamsung\s+NX", re.I),
    re.compile(r"\bDigimax\b", re.I),
    re.compile(r"\bGalaxy\s*Camera\b", re.I),
    # Ricoh digital
    re.compile(r"\bRicoh\s+GR\b", re.I),
    re.compile(r"\bRicoh\s+GXR\b", re.I),
    re.compile(r"\bRicoh\s+WG-", re.I),
    re.compile(r"\bRicoh\s+G\d{3}", re.I),
    re.compile(r"\bRicoh\s+Caplio\b", re.I),
    re.compile(r"\bGR\s*(?:III|IV|Digital)\b", re.I),  # Without brand prefix
    # Kodak digital
    re.compile(r"\bEasyShare\b", re.I),
    # HP digital
    re.compile(r"\bPhotosmart\b", re.I),
    re.compile(r"\bPhotoSmart\b", re.I),
    # Casio digital
    re.compile(r"\bExilim\b", re.I),
    # Other digital
    re.compile(r"\bGoPro\b", re.I),
    re.compile(r"\biPhone\b", re.I),
    re.compile(r"\bPixel\b", re.I),
    re.compile(r"\bPixii\b", re.I),
]

# Specific camera names/models that are digital (not caught by patterns)
DIGITAL_NAMES: frozenset[str] = frozenset({
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
    # Olympus digital compacts with alphanumeric suffixes
    "olympus c-730uz",
})

# Manufacturers that only made digital cameras (never analogue)
DIGITAL_ONLY_MANUFACTURERS: frozenset[str] = frozenset({
    "hewlett packard", "hp",
    "benq", "acer", "dell", "gateway", "mustek",
    "om system",
})


def is_digital_name(name: str) -> bool:
    """Check if a camera name matches digital camera patterns or exact names.

    Use this for collectors (flickr, collectiblend) where only the name is available.
    """
    if name.lower() in DIGITAL_NAMES:
        return True
    for pat in DIGITAL_PATTERNS:
        if pat.search(name):
            return True
    return False


def is_digital_camera(
    name: str,
    camera_type: str = "",
    manufacturer: str = "",
) -> bool:
    """Check if a camera is digital based on name, type, and manufacturer.

    Use this for merge.py where full record context is available.
    """
    if name.lower() in DIGITAL_NAMES:
        return True
    if manufacturer.lower() in DIGITAL_ONLY_MANUFACTURERS:
        return True
    text = f"{name} {camera_type}"
    for pat in DIGITAL_PATTERNS:
        if pat.search(text):
            return True
    return False
