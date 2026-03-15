"""Tests for iphoto_sizer.models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from iphoto_sizer.models import (
    BYTES_PER_GB,
    BYTES_PER_MB,
    CSV_COLUMNS,
    PhotoRecord,
    format_bytes,
)


class TestFormatBytes:
    def test_zero_bytes(self):
        assert format_bytes(0) == "0.00 MB"

    def test_one_megabyte(self):
        assert format_bytes(BYTES_PER_MB) == "1.00 MB"

    def test_fractional_megabytes(self):
        assert format_bytes(int(1.5 * BYTES_PER_MB)) == "1.50 MB"

    def test_just_below_one_gigabyte(self):
        result = format_bytes(BYTES_PER_GB - 1)
        assert "MB" in result

    def test_exactly_one_gigabyte(self):
        assert format_bytes(BYTES_PER_GB) == "1.00 GB"

    def test_multiple_gigabytes(self):
        assert format_bytes(int(2.5 * BYTES_PER_GB)) == "2.50 GB"

    def test_negative_raises_value_error(self):
        with pytest.raises(ValueError, match="non-negative"):
            format_bytes(-1)


class TestPhotoRecord:
    def test_valid_photo_record(self):
        record = PhotoRecord(
            filename="IMG_001.jpg",
            extension="jpg",
            media_type="photo",
            size_bytes=1024,
            size="0.00 MB",
            creation_date="2024-01-01 12:00:00",
            uuid="abc-123",
            icloud_status="local",
        )
        assert record.filename == "IMG_001.jpg"
        assert record.media_type == "photo"

    def test_frozen_model(self):
        record = PhotoRecord(
            filename="IMG_001.jpg",
            extension="jpg",
            media_type="photo",
            size_bytes=1024,
            size="0.00 MB",
            creation_date="",
            uuid="abc-123",
            icloud_status="local",
        )
        with pytest.raises(ValidationError):
            record.filename = "changed.jpg"  # type: ignore[misc]

    def test_size_bytes_rejects_negative(self):
        with pytest.raises(ValidationError):
            PhotoRecord(
                filename="test.jpg",
                extension="jpg",
                media_type="photo",
                size_bytes=-1,
                size="0.00 MB",
                creation_date="",
                uuid="abc",
                icloud_status="local",
            )

    def test_media_type_rejects_invalid(self):
        with pytest.raises(ValidationError):
            PhotoRecord(
                filename="test.jpg",
                extension="jpg",
                media_type="audio",  # type: ignore[arg-type]
                size_bytes=0,
                size="0.00 MB",
                creation_date="",
                uuid="abc",
                icloud_status="local",
            )

    def test_icloud_status_rejects_invalid(self):
        with pytest.raises(ValidationError):
            PhotoRecord(
                filename="test.jpg",
                extension="jpg",
                media_type="photo",
                size_bytes=0,
                size="0.00 MB",
                creation_date="",
                uuid="abc",
                icloud_status="syncing",  # type: ignore[arg-type]
            )

    def test_creation_date_coerces_datetime(self):
        dt = datetime(2024, 6, 15, 14, 30, 0, tzinfo=UTC)
        record = PhotoRecord(
            filename="test.jpg",
            extension="jpg",
            media_type="photo",
            size_bytes=0,
            size="0.00 MB",
            creation_date=dt,  # type: ignore[arg-type]
            uuid="abc",
            icloud_status="local",
        )
        assert record.creation_date == "2024-06-15 14:30:00"

    def test_creation_date_coerces_none(self):
        record = PhotoRecord(
            filename="test.jpg",
            extension="jpg",
            media_type="photo",
            size_bytes=0,
            size="0.00 MB",
            creation_date=None,  # type: ignore[arg-type]
            uuid="abc",
            icloud_status="local",
        )
        assert record.creation_date == ""

    def test_creation_date_passes_string_through(self):
        record = PhotoRecord(
            filename="test.jpg",
            extension="jpg",
            media_type="photo",
            size_bytes=0,
            size="0.00 MB",
            creation_date="already a string",
            uuid="abc",
            icloud_status="local",
        )
        assert record.creation_date == "already a string"

    def test_size_bytes_coerces_string_to_int(self):
        record = PhotoRecord(
            filename="test.jpg",
            extension="jpg",
            media_type="photo",
            size_bytes="12345",  # type: ignore[arg-type]
            size="0.00 MB",
            creation_date="",
            uuid="abc",
            icloud_status="local",
        )
        assert record.size_bytes == 12345
        assert isinstance(record.size_bytes, int)


class TestCSVColumns:
    def test_columns_match_model_fields(self):
        assert tuple(PhotoRecord.model_fields.keys()) == CSV_COLUMNS

    def test_expected_columns_present(self):
        expected = {"filename", "extension", "media_type", "size_bytes", "size",
                    "creation_date", "uuid", "icloud_status"}
        assert set(CSV_COLUMNS) == expected
