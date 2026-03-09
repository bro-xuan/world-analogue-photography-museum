import pytest
from unittest.mock import patch

from src.normalization.merge import _merge_entities, CAMERA_MERGE_FIELDS


@pytest.fixture
def _mock_merged_dir(tmp_path):
    with patch("src.normalization.merge.MERGED_DIR", tmp_path):
        yield tmp_path


def test_qid_match(make_camera, _mock_merged_dir):
    records = [
        make_camera(name="AE-1", manufacturer="Canon", wikidata_qid="Q123",
                     camera_type="SLR"),
        make_camera(name="AE-1", manufacturer="Canon", wikidata_qid="Q123",
                     year_introduced=1976),
    ]
    result, stats = _merge_entities(records, CAMERA_MERGE_FIELDS)
    assert len(result) == 1
    assert stats["qid_matches"] == 1
    assert result[0]["camera_type"] == "SLR"
    assert result[0]["year_introduced"] == 1976


def test_exact_key_match(make_camera, _mock_merged_dir):
    records = [
        make_camera(name="AE-1", manufacturer="Canon",
                     sources=[{"source": "wikidata", "source_id": "w1"}]),
        make_camera(name="AE-1", manufacturer="Canon",
                     sources=[{"source": "flickr", "source_id": "f1"}]),
    ]
    result, stats = _merge_entities(records, CAMERA_MERGE_FIELDS)
    assert len(result) == 1
    assert stats["exact_matches"] == 1


def test_exact_key_match_different_aliases(make_camera, _mock_merged_dir):
    """Nippon Kogaku and Nikon should resolve to same key."""
    records = [
        make_camera(name="F2", manufacturer="Nikon",
                     sources=[{"source": "wikidata", "source_id": "w1"}]),
        make_camera(name="F2", manufacturer="Nippon Kogaku",
                     sources=[{"source": "flickr", "source_id": "f1"}]),
    ]
    result, stats = _merge_entities(records, CAMERA_MERGE_FIELDS)
    assert len(result) == 1
    assert stats["exact_matches"] == 1


def test_fuzzy_match(make_camera, _mock_merged_dir):
    records = [
        make_camera(name="Canon AE-1 Program", manufacturer="Canon",
                     sources=[{"source": "wikidata", "source_id": "w1"}]),
        make_camera(name="Canon AE-1 Programme", manufacturer="Canon",
                     sources=[{"source": "flickr", "source_id": "f1"}]),
    ]
    result, stats = _merge_entities(records, CAMERA_MERGE_FIELDS)
    assert len(result) == 1
    assert stats["fuzzy_matches"] == 1


def test_different_manufacturers_no_fuzzy(make_camera, _mock_merged_dir):
    records = [
        make_camera(name="Super Camera X100", manufacturer="Canon",
                     sources=[{"source": "wikidata", "source_id": "w1"}]),
        make_camera(name="Super Camera X100", manufacturer="Nikon",
                     sources=[{"source": "wikidata", "source_id": "w2"}]),
    ]
    result, stats = _merge_entities(records, CAMERA_MERGE_FIELDS)
    assert len(result) == 2
    assert stats["fuzzy_matches"] == 0


def test_uuid_assigned(make_camera, _mock_merged_dir):
    records = [make_camera(name="AE-1", manufacturer="Canon")]
    result, stats = _merge_entities(records, CAMERA_MERGE_FIELDS)
    assert result[0]["id"] is not None
    assert len(result[0]["id"]) == 36  # UUID format


def test_higher_priority_source_wins_on_fuzzy(make_camera, _mock_merged_dir):
    """When fuzzy matching, the record from the higher-priority source should be the base."""
    records = [
        make_camera(name="Canon AE-1 Programme", manufacturer="Canon",
                     camera_type="SLR",
                     sources=[{"source": "flickr", "source_id": "f1"}]),
        make_camera(name="Canon AE-1 Program", manufacturer="Canon",
                     camera_type="Rangefinder",
                     sources=[{"source": "wikidata", "source_id": "w1"}]),
    ]
    result, stats = _merge_entities(records, CAMERA_MERGE_FIELDS)
    assert len(result) == 1
    # Wikidata has higher priority, so its camera_type should be the base
    assert result[0]["camera_type"] == "Rangefinder"
