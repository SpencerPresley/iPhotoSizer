"""Tests for iphoto_sizer.core."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from iphoto_sizer.core import apply_filters, load_photos_db, photo_to_record
from iphoto_sizer.models import PhotoRecord


def _fake_photo(**overrides: object) -> SimpleNamespace:
    """Create a fake osxphotos.PhotoInfo-like object with sensible defaults."""
    defaults = {
        "original_filename": "IMG_001.jpg",
        "original_filesize": 5_000_000,
        "ismovie": False,
        "date": datetime(2024, 6, 15, 14, 30, 0),
        "uuid": "ABC-123-DEF",
        "ismissing": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestPhotoToRecord:
    def test_basic_photo(self):
        photo = _fake_photo()
        record = photo_to_record(photo)

        assert isinstance(record, PhotoRecord)
        assert record.filename == "IMG_001.jpg"
        assert record.extension == "jpg"
        assert record.media_type == "photo"
        assert record.size_bytes == 5_000_000
        assert record.uuid == "ABC-123-DEF"
        assert record.icloud_status == "local"

    def test_video(self):
        photo = _fake_photo(ismovie=True, original_filename="clip.mov")
        record = photo_to_record(photo)

        assert record.media_type == "video"
        assert record.extension == "mov"

    def test_cloud_only(self):
        photo = _fake_photo(ismissing=True)
        record = photo_to_record(photo)

        assert record.icloud_status == "cloud-only"

    def test_none_filesize_defaults_to_zero(self):
        photo = _fake_photo(original_filesize=None)
        record = photo_to_record(photo)

        assert record.size_bytes == 0

    def test_none_filename_defaults_to_unknown(self):
        photo = _fake_photo(original_filename=None)
        record = photo_to_record(photo)

        assert record.filename == "unknown"
        assert record.extension == ""

    def test_none_date_produces_empty_string(self):
        photo = _fake_photo(date=None)
        record = photo_to_record(photo)

        assert record.creation_date == ""

    def test_date_formatted_correctly(self):
        photo = _fake_photo(date=datetime(2024, 12, 25, 8, 0, 0))
        record = photo_to_record(photo)

        assert record.creation_date == "2024-12-25 08:00:00"

    def test_extension_is_lowercase(self):
        photo = _fake_photo(original_filename="photo.HEIC")
        record = photo_to_record(photo)

        assert record.extension == "heic"

    def test_human_readable_size(self):
        photo = _fake_photo(original_filesize=1024**3)
        record = photo_to_record(photo)

        assert record.size == "1.00 GB"

    def test_negative_filesize_raises(self):
        photo = _fake_photo(original_filesize=-100)
        with pytest.raises(ValueError, match="non-negative"):
            photo_to_record(photo)


class TestApplyFilters:
    def _make_records(self, sizes: list[int]) -> list[PhotoRecord]:
        return [
            PhotoRecord(
                filename=f"file_{i}.jpg",
                extension="jpg",
                media_type="photo",
                size_bytes=size,
                size="0.00 MB",
                creation_date="",
                uuid=f"uuid-{i}",
                icloud_status="local",
            )
            for i, size in enumerate(sizes)
        ]

    def test_no_filter_returns_all(self):
        records = self._make_records([100, 200, 300])
        result = apply_filters(records)

        assert len(result) == 3

    def test_zero_threshold_returns_all(self):
        records = self._make_records([100, 200, 300])
        result = apply_filters(records, min_size_bytes=0)

        assert len(result) == 3

    def test_filters_below_threshold(self):
        records = self._make_records([100, 200, 300])
        result = apply_filters(records, min_size_bytes=200)

        assert len(result) == 2
        assert all(r.size_bytes >= 200 for r in result)

    def test_threshold_above_all_returns_empty(self):
        records = self._make_records([100, 200, 300])
        result = apply_filters(records, min_size_bytes=1000)

        assert result == []

    def test_empty_input_returns_empty(self):
        result = apply_filters([], min_size_bytes=100)

        assert result == []

    def test_exact_threshold_is_included(self):
        records = self._make_records([100, 200, 300])
        result = apply_filters(records, min_size_bytes=200)

        sizes = [r.size_bytes for r in result]
        assert 200 in sizes


class TestLoadPhotosDB:
    def test_exits_on_failure(self):
        with patch("iphoto_sizer.core.osxphotos.PhotosDB", side_effect=RuntimeError("no access")):
            with pytest.raises(SystemExit) as exc_info:
                load_photos_db()
            assert exc_info.value.code == 1

    def test_prints_full_disk_access_hint_on_failure(self, capsys):
        with patch("iphoto_sizer.core.osxphotos.PhotosDB", side_effect=RuntimeError("no access")):
            with pytest.raises(SystemExit):
                load_photos_db()
        stderr = capsys.readouterr().err
        assert "Full Disk Access" in stderr

    def test_returns_db_on_success(self):
        mock_db = MagicMock()
        with patch("iphoto_sizer.core.osxphotos.PhotosDB", return_value=mock_db):
            result = load_photos_db()
        assert result is mock_db

    def test_prints_loading_message(self, capsys):
        with patch("iphoto_sizer.core.osxphotos.PhotosDB"):
            load_photos_db()
        stderr = capsys.readouterr().err
        assert "Loading Photos library" in stderr
        assert "Library loaded" in stderr
