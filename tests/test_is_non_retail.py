import pytest

from src.normalization.merge import _is_non_retail


@pytest.mark.parametrize("record", [
    # Military/space keywords
    {"name": "Satellite Camera", "description": ""},
    {"name": "Military reconnaissance camera", "description": ""},
    {"name": "Mars Rover Camera", "description": ""},
    {"name": "Hubble Wide Field Camera", "description": ""},
    # Novelty/toy cameras
    {"name": "Barbie Fun Camera", "description": ""},
    {"name": "Pokemon Snap Camera", "description": ""},
    {"name": "Hello Kitty Camera", "description": ""},
    {"name": "Star Wars Camera", "description": ""},
    {"name": "Snoopy Camera", "description": ""},
    {"name": "Disney Princess Camera", "description": ""},
    # Non-retail manufacturers
    {"name": "Some Camera", "description": "", "manufacturer_normalized": "nintendo"},
    {"name": "Some Camera", "description": "", "manufacturer_normalized": "general electric"},
    {"name": "Some Camera", "description": "", "manufacturer_normalized": "ball aerospace & technologies"},
    # Wiki noise manufacturers
    {"name": "Some Camera", "description": "", "manufacturer_normalized": "slr"},
    {"name": "Some Camera", "description": "", "manufacturer_normalized": "compact camera"},
    # Collectiblend country categories
    {"name": "Some Camera", "description": "", "manufacturer_normalized": "japan"},
    {"name": "Some Camera", "description": "", "manufacturer_normalized": "germany"},
    # Keywords in description
    {"name": "Some Camera", "description": "x-ray imaging device"},
    {"name": "Camera System", "description": "drone camera for surveillance"},
], ids=lambda r: r.get("name", "") + "|" + (r.get("manufacturer_normalized", "") or ""))
def test_is_non_retail_true(record):
    assert _is_non_retail(record)


@pytest.mark.parametrize("record", [
    {"name": "Canon AE-1", "description": "A 35mm film SLR", "manufacturer_normalized": "Canon"},
    {"name": "Nikon F2", "description": "", "manufacturer_normalized": "Nikon"},
    {"name": "Leica M6", "description": "Rangefinder camera", "manufacturer_normalized": "Leica"},
    {"name": "Holga 120N", "description": "Toy camera", "manufacturer_normalized": "Holga"},
    {"name": "Seagull DF-1", "description": "", "manufacturer_normalized": "Seagull"},
])
def test_is_non_retail_false(record):
    assert not _is_non_retail(record)
