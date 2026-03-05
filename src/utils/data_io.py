"""Utilities for saving and loading collected data."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MERGED_DIR = DATA_DIR / "merged"
IMAGES_DIR = DATA_DIR / "images"


def save_records(records: list[BaseModel], source: str, entity_type: str) -> Path:
    """Save a list of Pydantic models to a JSON file in data/raw/{source}/."""
    out_dir = RAW_DIR / source
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{entity_type}.json"
    data = [r.model_dump(exclude_none=True) for r in records]
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Saved {len(data)} {entity_type} records to {out_path}")
    return out_path


def load_records(source: str, entity_type: str) -> list[dict]:
    """Load records from a JSON file in data/raw/{source}/."""
    path = RAW_DIR / source / f"{entity_type}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_merged(records: list[dict], entity_type: str) -> Path:
    """Save merged records to data/merged/."""
    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MERGED_DIR / f"{entity_type}.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False))
    print(f"Saved {len(records)} merged {entity_type} records to {out_path}")
    return out_path
