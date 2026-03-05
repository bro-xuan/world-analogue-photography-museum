"""Canonical data models for cameras and films."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceReference(BaseModel):
    """Tracks where a piece of data came from."""
    source: str  # e.g. "wikidata", "flickr", "wikipedia"
    source_id: str | None = None  # e.g. Wikidata QID "Q12345"
    source_url: str | None = None
    retrieved_at: str | None = None  # ISO 8601


class ImageReference(BaseModel):
    """An image associated with a camera or film."""
    url: str
    source: str
    license: str | None = None
    caption: str | None = None
    is_hosted: bool = False  # True = we host it; False = link only
    local_path: str | None = None


class Camera(BaseModel):
    """Canonical camera model."""
    id: str | None = None  # Internal UUID, assigned during merge
    name: str
    manufacturer: str
    manufacturer_normalized: str | None = None
    manufacturer_country: str | None = None

    # Identifiers
    wikidata_qid: str | None = None
    flickr_id: str | None = None

    # Classification
    camera_type: str | None = None  # SLR, rangefinder, TLR, point-and-shoot, etc.
    film_format: str | None = None  # 35mm, 120, 4x5, instant, etc.

    # Timeline
    year_introduced: int | None = None
    year_discontinued: int | None = None
    launch_date: str | None = None  # ISO 8601 date or year string, e.g. "1959" or "1959-03-15"

    # Specs
    lens_mount: str | None = None
    shutter_speed_range: str | None = None
    metering: str | None = None
    weight_g: int | None = None
    dimensions: str | None = None
    battery: str | None = None

    # Pricing
    price_launch_usd: float | None = None        # Original MSRP in USD at launch
    price_adjusted_usd: float | None = None       # Launch price adjusted to 2024 USD
    price_market_usd: float | None = None         # Current collector market value in USD

    # Media
    images: list[ImageReference] = Field(default_factory=list)

    # Provenance
    sources: list[SourceReference] = Field(default_factory=list)
    description: str | None = None


class Film(BaseModel):
    """Canonical film emulsion model."""
    id: str | None = None
    name: str
    manufacturer: str
    manufacturer_normalized: str | None = None

    # Identifiers
    wikidata_qid: str | None = None

    # Classification
    film_type: str | None = None  # color negative, color reversal, B&W, instant
    iso_speed: int | None = None
    available_formats: list[str] = Field(default_factory=list)  # 35mm, 120, 4x5, etc.

    # Status
    is_current: bool | None = None  # Still in production?
    year_introduced: int | None = None
    year_discontinued: int | None = None
    launch_date: str | None = None

    # Characteristics
    grain: str | None = None  # fine, medium, coarse
    color_rendition: str | None = None

    # Media
    images: list[ImageReference] = Field(default_factory=list)

    # Provenance
    sources: list[SourceReference] = Field(default_factory=list)
    description: str | None = None
