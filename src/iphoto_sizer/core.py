"""Core business logic for reading and transforming Photos library data."""

import sys
from pathlib import Path

import osxphotos

from iphoto_sizer.models import PhotoRecord, format_bytes

_UNKNOWN_FILENAME = "unknown"


def photo_to_record(photo: osxphotos.PhotoInfo) -> PhotoRecord:
    """Transform an osxphotos ``PhotoInfo`` object into a ``PhotoRecord``.

    Args:
        photo (osxphotos.PhotoInfo): A single item from the Photos library.

    Returns:
        PhotoRecord: Flat record ready for CSV output and sorting.
    """
    filename = str(photo.original_filename or _UNKNOWN_FILENAME)
    # original_filesize can be None at runtime for photos not yet indexed
    # by iCloud, despite what osxphotos type stubs declare
    raw_size = photo.original_filesize
    size_bytes = int(raw_size) if raw_size is not None else 0  # pyright: ignore[reportUnnecessaryComparison]

    # Pydantic validates types, enforces size_bytes >= 0, and restricts
    # media_type / icloud_status to their allowed literal values
    return PhotoRecord(
        filename=filename,
        extension=Path(filename).suffix.lstrip(".").lower(),
        media_type="video" if photo.ismovie else "photo",
        size_bytes=size_bytes,
        size=format_bytes(size_bytes),
        # The model's field_validator handles datetime/str/None coercion
        creation_date=photo.date,  # type: ignore[arg-type]
        uuid=str(photo.uuid),
        # ismissing indicates the original file isn't on disk,
        # which typically means it's stored only in iCloud
        icloud_status="cloud-only" if photo.ismissing else "local",
    )


def load_photos_db() -> osxphotos.PhotosDB:
    """Open the Photos library database.

    Prints a loading message since initial database construction can take
    15-20 seconds for large libraries.

    Returns:
        osxphotos.PhotosDB: The loaded database object.

    Raises:
        SystemExit: If the database cannot be opened, typically due to
                    missing Full Disk Access permissions.
    """
    print("Loading Photos library (this may take 15-20 seconds)...", file=sys.stderr)
    try:
        db = osxphotos.PhotosDB()
    except Exception as e:
        print(f"Failed to open Photos library: {e}", file=sys.stderr)
        # PhotosDB needs access to the Photos library package, which is
        # protected by macOS privacy controls on Catalina and later
        print(
            "Grant Full Disk Access: System Settings > Privacy & Security > Full Disk Access",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Library loaded.", file=sys.stderr)
    return db


def apply_filters(
    records: list[PhotoRecord],
    min_size_bytes: float = 0,
) -> list[PhotoRecord]:
    """Apply filters to the record list.

    Add new keyword arguments here for additional filters (e.g. media
    type, date range, iCloud status) without modifying the CLI layer.

    Args:
        records (list[PhotoRecord]): The unfiltered record list.
        min_size_bytes (float): Exclude items smaller than this. Defaults
                                to 0 (include all).

    Returns:
        list[PhotoRecord]: The filtered record list.
    """
    if min_size_bytes > 0:
        records = [r for r in records if r.size_bytes >= min_size_bytes]
    return records
