from src.normalization.merge import _merge_record, CAMERA_MERGE_FIELDS


def test_overlay_fills_empty_fields():
    base = {"name": "Canon AE-1", "camera_type": None, "year_introduced": None,
            "images": [], "sources": []}
    overlay = {"name": "Canon AE-1", "camera_type": "SLR", "year_introduced": 1976,
               "images": [], "sources": []}
    result = _merge_record(base, overlay, CAMERA_MERGE_FIELDS)
    assert result["camera_type"] == "SLR"
    assert result["year_introduced"] == 1976


def test_base_non_none_fields_preserved():
    base = {"name": "Canon AE-1", "camera_type": "SLR", "year_introduced": 1976,
            "images": [], "sources": []}
    overlay = {"name": "Canon AE-1", "camera_type": "Compact", "year_introduced": 1977,
               "images": [], "sources": []}
    result = _merge_record(base, overlay, CAMERA_MERGE_FIELDS)
    assert result["camera_type"] == "SLR"
    assert result["year_introduced"] == 1976


def test_overlay_fills_empty_string():
    base = {"name": "X", "camera_type": "", "images": [], "sources": []}
    overlay = {"name": "X", "camera_type": "SLR", "images": [], "sources": []}
    result = _merge_record(base, overlay, CAMERA_MERGE_FIELDS)
    assert result["camera_type"] == "SLR"


def test_image_dedup_by_url():
    base = {"name": "X",
            "images": [{"url": "http://a.jpg", "source": "wiki"}],
            "sources": []}
    overlay = {"name": "X",
               "images": [{"url": "http://a.jpg", "source": "flickr"},
                          {"url": "http://b.jpg", "source": "flickr"}],
               "sources": []}
    result = _merge_record(base, overlay, [])
    urls = [img["url"] for img in result["images"]]
    assert len(urls) == 2
    assert "http://a.jpg" in urls
    assert "http://b.jpg" in urls


def test_source_dedup_by_source_and_id():
    base = {"name": "X", "images": [],
            "sources": [{"source": "wikidata", "source_id": "Q123"}]}
    overlay = {"name": "X", "images": [],
               "sources": [{"source": "wikidata", "source_id": "Q123"},
                           {"source": "flickr", "source_id": "f1"}]}
    result = _merge_record(base, overlay, [])
    assert len(result["sources"]) == 2


def test_qid_from_overlay():
    base = {"name": "X", "wikidata_qid": None, "images": [], "sources": []}
    overlay = {"name": "X", "wikidata_qid": "Q12345", "images": [], "sources": []}
    result = _merge_record(base, overlay, [])
    assert result["wikidata_qid"] == "Q12345"


def test_qid_not_overwritten():
    base = {"name": "X", "wikidata_qid": "Q111", "images": [], "sources": []}
    overlay = {"name": "X", "wikidata_qid": "Q222", "images": [], "sources": []}
    result = _merge_record(base, overlay, [])
    assert result["wikidata_qid"] == "Q111"
