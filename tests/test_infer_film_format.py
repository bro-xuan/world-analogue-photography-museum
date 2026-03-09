import pytest

from src.normalization.merge import _normalize_film_format, _infer_film_format


@pytest.mark.parametrize("raw,expected", [
    # Standard format normalization
    ("35mm", "135"),
    ("35 mm", "135"),
    ("Type 135", "135"),
    ("full frame", "135"),
    # Medium format
    ("120", "120"),
    ("medium format", "120"),
    # Instant
    ("instant", "Instant"),
    ("Instant film", "Instant"),
    ("Polaroid", "Instant"),
    ("Instax", "Instant"),
    # Other formats
    ("110", "110"),
    ("126", "126"),
    ("127", "127"),
    ("220", "220"),
    ("APS", "APS"),
    ("Disc", "Disc"),
    ("Half-frame", "Half-frame"),
    ("subminiature", "Subminiature"),
    # Large format
    ("4x5", "4x5"),
    ("8x10", "8x10"),
    ("large format", "4x5"),
    ("sheet film", "4x5"),
    # Edge cases
    (None, None),
    ("", None),
    # Unknown format returned as-is
    ("weird format", "weird format"),
])
def test_normalize_film_format(raw, expected):
    assert _normalize_film_format(raw) == expected


@pytest.mark.parametrize("record,expected", [
    # Tier 1: camera_type mapping
    ({"name": "Canon AE-1", "camera_type": "SLR"}, "135"),
    ({"name": "Polaroid 600", "camera_type": "Instant"}, "Instant"),
    ({"name": "Graflex Crown Graphic", "camera_type": "View camera"}, "4x5"),
    ({"name": "Mamiya RB67", "camera_type": "Medium format"}, "120"),
    ({"name": "Generic", "camera_type": "Box camera"}, "120"),
    ({"name": "Kodak Retina", "camera_type": "Point-and-shoot"}, "135"),
    ({"name": "Contax G2", "camera_type": "Rangefinder"}, "135"),
    # Tier 2: name-based patterns
    ({"name": "Instax Mini 11", "camera_type": ""}, "Instant"),
    ({"name": "Rolleiflex 2.8F", "camera_type": ""}, "120"),
    ({"name": "Speed Graphic 4x5", "camera_type": ""}, "4x5"),
    # Tier 3: medium format prefixes
    ({"name": "Mamiya RB67 Pro S", "camera_type": "", "manufacturer_normalized": ""}, "120"),
    ({"name": "Hasselblad 500C/M", "camera_type": "", "manufacturer_normalized": ""}, "120"),
    # Tier 4: manufacturer defaults
    ({"name": "Unknown", "camera_type": "", "manufacturer_normalized": "Polaroid"}, "Instant"),
    ({"name": "Unknown", "camera_type": "", "manufacturer_normalized": "Minox"}, "Subminiature"),
    ({"name": "Unknown", "camera_type": "", "manufacturer_normalized": "Graflex"}, "4x5"),
    ({"name": "Unknown", "camera_type": "", "manufacturer_normalized": "Hasselblad"}, "120"),
    # Tier 5: major 35mm brands
    ({"name": "Some Model", "camera_type": "", "manufacturer_normalized": "Nikon"}, "135"),
    ({"name": "Some Model", "camera_type": "", "manufacturer_normalized": "Canon"}, "135"),
    ({"name": "Some Model", "camera_type": "", "manufacturer_normalized": "Leica"}, "135"),
])
def test_infer_film_format(record, expected):
    assert _infer_film_format(record) == expected
