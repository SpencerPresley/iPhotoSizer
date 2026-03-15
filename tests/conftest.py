"""Shared test factories and fixtures."""

from datetime import UTC, datetime
from types import SimpleNamespace

from iphoto_sizer.models import PhotoRecord


def make_fake_photo(**overrides: object) -> SimpleNamespace:
    """Create a fake osxphotos.PhotoInfo-like object with sensible defaults."""
    defaults: dict[str, object] = {
        "original_filename": "IMG_001.jpg",
        "original_filesize": 5_000_000,
        "ismovie": False,
        "date": datetime(2024, 6, 15, 14, 30, 0, tzinfo=UTC),
        "uuid": "ABC-123-DEF",
        "ismissing": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_record(**overrides: object) -> PhotoRecord:
    """Create a PhotoRecord with sensible defaults."""
    defaults: dict[str, object] = {
        "filename": "IMG_001.jpg",
        "extension": "jpg",
        "media_type": "photo",
        "size_bytes": 1024,
        "size": "0.00 MB",
        "creation_date": "2024-01-01 12:00:00",
        "uuid": "abc-123",
        "icloud_status": "local",
    }
    defaults.update(overrides)
    return PhotoRecord(**defaults)


def make_record_dict(**overrides: object) -> dict[str, object]:
    """Create a PhotoRecord-shaped dict for API testing."""
    record = make_record(**overrides)
    return record.model_dump()
