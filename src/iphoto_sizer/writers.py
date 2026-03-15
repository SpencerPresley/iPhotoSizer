"""Output format writers conforming to the ``RecordWriter`` protocol."""

import csv
import json
from pathlib import Path

from iphoto_sizer.models import CSV_COLUMNS, PhotoRecord, RecordWriter

_JSON_INDENT = 4


def write_csv(records: list[PhotoRecord], output_path: Path) -> None:
    """Write photo records to a CSV file.

    Args:
        records (list[PhotoRecord]): Records to write, assumed pre-sorted.
        output_path (Path): Destination file path for the CSV.
    """
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.model_dump())


def write_json(records: list[PhotoRecord], output_path: Path) -> None:
    """Write photo records to a JSON file.

    Args:
        records (list[PhotoRecord]): Records to write, assumed pre-sorted.
        output_path (Path): Destination file path for the JSON.
    """
    with output_path.open("w") as f:
        json.dump([record.model_dump() for record in records], f, indent=_JSON_INDENT)


FORMAT_WRITERS: dict[str, RecordWriter] = {
    "csv": write_csv,
    "json": write_json,
}
