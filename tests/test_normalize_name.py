import pytest

from src.normalization.merge import _normalize_name


@pytest.mark.parametrize("input_name,expected", [
    # Lowercasing
    ("Canon AE-1", "canon ae-1"),
    ("NIKON F2", "nikon f2"),
    # Whitespace strip + collapse
    ("  Leica M6  ", "leica m6"),
    ("Canon  AE-1  Program", "canon ae-1 program"),
    # Trademark removal
    ("Canon™ EOS", "canon eos"),
    ("Nikon® F3", "nikon f3"),
    ("Olympus© OM-1", "olympus om-1"),
    # Chinese characters preserved
    ("海鸥 DF-1", "海鸥 df-1"),
    # Empty string
    ("", ""),
])
def test_normalize_name(input_name, expected):
    assert _normalize_name(input_name) == expected
