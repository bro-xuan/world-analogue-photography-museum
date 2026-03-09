import pytest

from src.normalization.manufacturers import normalize_manufacturer, get_manufacturer_country


@pytest.mark.parametrize("input_name,expected", [
    # Basic aliases
    ("Nippon Kogaku", "Nikon"),
    ("nippon kogaku", "Nikon"),
    ("Canon Camera Co.", "Canon"),
    ("canon inc.", "Canon"),
    ("Asahi Optical", "Pentax"),
    ("asahi pentax", "Pentax"),
    ("Ernst Leitz", "Leica"),
    ("Fuji Photo Film", "Fujifilm"),
    ("Eastman Kodak", "Kodak"),
    # Suffix stripping
    ("Nikon Corporation", "Nikon"),
    ("Canon Inc.", "Canon"),
    ("Leica Camera AG", "Leica"),
    ("Sigma Corporation", "Sigma"),
    # Chinese brands
    ("海鸥", "Seagull"),
    ("凤凰", "Phenix"),
    ("珠江", "Pearl River"),
    ("长城", "Great Wall"),
    ("红旗", "Red Flag"),
    # Soviet/Russian
    ("kmz", "Zenit"),
    ("fed factory", "FED"),
    ("arsenal", "Kiev"),
    # Pipe handling (camerawiki bug)
    ("Canon|some junk text", "Canon"),
    # Identity (already canonical)
    ("Nikon", "Nikon"),
    ("Canon", "Canon"),
    ("Leica", "Leica"),
    # Unknown manufacturer returned as-is
    ("Unknown Brand", "Unknown Brand"),
    ("", ""),
])
def test_normalize_manufacturer(input_name, expected):
    assert normalize_manufacturer(input_name) == expected


@pytest.mark.parametrize("input_name,expected", [
    ("Nikon", "Japan"),
    ("Canon", "Japan"),
    ("Leica", "Germany"),
    ("Kodak", "USA"),
    ("Seagull", "China"),
    ("海鸥", "China"),
    ("Hasselblad", "Sweden"),
    ("Polaroid", "USA"),
    ("Zenit", "Russia"),
    ("FED", "Ukraine"),
    ("Praktica", "Germany"),
    ("Unknown", None),
])
def test_get_manufacturer_country(input_name, expected):
    assert get_manufacturer_country(input_name) == expected
