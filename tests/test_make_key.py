import pytest

from src.normalization.merge import _make_key


@pytest.mark.parametrize("manufacturer,name,expected", [
    # Basic key creation
    ("Canon", "AE-1", "canon|ae-1"),
    # Alias resolution
    ("Nippon Kogaku", "F2", "nikon|f2"),
    ("canon inc.", "AE-1", "canon|ae-1"),
    ("Asahi Optical", "K1000", "pentax|k1000"),
    ("Canon Camera Co.", "AE-1", "canon|ae-1"),
    # Chinese manufacturer alias
    ("海鸥", "DF-1", "seagull|df-1"),
    # Case insensitive
    ("NIKON", "F3", "nikon|f3"),
    # Suffix stripping via normalize_manufacturer
    ("Nikon Corporation", "FM2", "nikon|fm2"),
])
def test_make_key(manufacturer, name, expected):
    assert _make_key(manufacturer, name) == expected
