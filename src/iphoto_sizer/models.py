"""Data models, types, and constants for the iCloud file sorter."""

from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, get_args

from pydantic import BaseModel, Field, field_validator

BYTES_PER_MB = 1024**2
BYTES_PER_GB = 1024**3
_SIZE_DECIMAL_PLACES = 2
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

OutputFormat = Literal["csv", "json"]
DEFAULT_OUTPUT_STEM = "photos_report"
DEFAULT_FORMAT: OutputFormat = "csv"
DEFAULT_OUTPUT_FILE = f"{DEFAULT_OUTPUT_STEM}.{DEFAULT_FORMAT}"
SUPPORTED_FORMATS = get_args(OutputFormat)

MEDIA_TYPE_PHOTO = "photo"
MEDIA_TYPE_VIDEO = "video"
ICLOUD_STATUS_LOCAL = "local"
ICLOUD_STATUS_CLOUD_ONLY = "cloud-only"


class PhotoRecord(BaseModel):
    """A single photo or video entry extracted from the Photos library.

    Pydantic coerces incoming values to the declared types, so a filesize
    returned as a string from SQLite will be cast to ``int`` rather than
    silently producing bad data downstream.

    Attributes:
        filename (str): Original filename at import time.
        extension (str): Lowercase file extension without the leading dot.
        media_type (str): Either ``"photo"`` or ``"video"``.
        size_bytes (int): Raw file size in bytes for sorting and filtering.
        size (str): Human-readable size string (e.g. ``"150.23 MB"``).
        creation_date (str): Creation timestamp as ``YYYY-MM-DD HH:MM:SS``,
                             or empty string if unavailable.
        uuid (str): Photos library UUID for programmatic operations.
        icloud_status (str): ``"local"`` if the original is on disk,
                             ``"cloud-only"`` if it exists only in iCloud.
    """

    model_config = {"frozen": True}

    filename: str
    extension: str
    media_type: Literal["photo", "video"]
    size_bytes: int = Field(ge=0)
    size: str
    creation_date: str
    uuid: str
    icloud_status: Literal["local", "cloud-only"]

    @field_validator("creation_date", mode="before")
    @classmethod
    def coerce_creation_date(cls, value: object) -> str:
        """Accept ``datetime``, ``str``, or ``None`` and normalize to a string."""
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime(_DATE_FORMAT)
        return str(value)


# Derived from the model so columns can never drift out of sync
CSV_COLUMNS = tuple(PhotoRecord.model_fields.keys())


class RecordWriter(Protocol):
    """Contract for output format writers.

    Any callable matching this signature can be used as a writer.
    """

    def __call__(self, records: list[PhotoRecord], output_path: Path) -> None:
        """Write records to the given output path."""
        ...


def format_bytes(size_bytes: int) -> str:
    """Convert a byte count into a human-readable size string.

    Displays in GB for sizes at or above 1 GB, otherwise in MB.

    Args:
        size_bytes (int): File size in bytes.

    Returns:
        str: Formatted string like ``"1.50 GB"`` or ``"230.45 MB"``.

    Raises:
        ValueError: If ``size_bytes`` is negative, indicating a data
                    integrity issue upstream.
    """
    if size_bytes < 0:
        msg = f"size_bytes must be non-negative, got {size_bytes}"
        raise ValueError(msg)
    if size_bytes >= BYTES_PER_GB:
        return f"{size_bytes / BYTES_PER_GB:.{_SIZE_DECIMAL_PLACES}f} GB"
    return f"{size_bytes / BYTES_PER_MB:.{_SIZE_DECIMAL_PLACES}f} MB"
