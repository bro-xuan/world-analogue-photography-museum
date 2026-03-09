import pytest


@pytest.fixture
def make_camera():
    """Factory fixture returning minimal camera dicts."""

    def _make(**overrides):
        base = {
            "name": "",
            "manufacturer": "",
            "manufacturer_normalized": "",
            "camera_type": None,
            "film_format": None,
            "year_introduced": None,
            "year_discontinued": None,
            "launch_date": None,
            "lens_mount": None,
            "shutter_speed_range": None,
            "metering": None,
            "weight_g": None,
            "dimensions": None,
            "battery": None,
            "description": None,
            "manufacturer_country": None,
            "wikidata_qid": None,
            "flickr_id": None,
            "images": [],
            "sources": [],
        }
        base.update(overrides)
        return base

    return _make


@pytest.fixture
def make_film():
    """Factory fixture returning minimal film dicts."""

    def _make(**overrides):
        base = {
            "name": "",
            "manufacturer": "",
            "manufacturer_normalized": "",
            "film_type": None,
            "iso_speed": None,
            "available_formats": None,
            "is_current": None,
            "year_introduced": None,
            "year_discontinued": None,
            "launch_date": None,
            "grain": None,
            "color_rendition": None,
            "description": None,
            "wikidata_qid": None,
            "images": [],
            "sources": [],
        }
        base.update(overrides)
        return base

    return _make
