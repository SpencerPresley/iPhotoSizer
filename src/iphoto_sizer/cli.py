"""CLI entry point for iphoto-sizer.

.. code-block:: bash

    # Export all items to photos_report.csv in the current directory
    iphoto-sizer

    # Or run as a module
    python -m iphoto_sizer

    # Export only items larger than 100 MB
    iphoto-sizer --min-size-mb 100

    # Export to a custom path
    iphoto-sizer -o ~/Desktop/large_files.csv

    # Export as JSON
    iphoto-sizer -f json -o ~/Desktop/photos.json

    # Combine options
    iphoto-sizer --min-size-mb 500 -o ~/Desktop/big_ones.csv
"""

import argparse
import shutil
import sys
from pathlib import Path

from iphoto_sizer.core import load_photos_db, scan_library
from iphoto_sizer.models import (
    BYTES_PER_MB,
    DEFAULT_FORMAT,
    DEFAULT_OUTPUT_FILE,
    SUPPORTED_FORMATS,
    PhotoRecord,
    format_bytes,
)
from iphoto_sizer.writers import FORMAT_WRITERS

_EXIT_CODE_ERROR = 1
_EXIT_CODE_INTERRUPTED = 130
_MIN_FREE_DISK_SPACE_MB = 50

# Summary table column widths
_COL_WIDTH_RANK = 3
_COL_WIDTH_FILENAME = 40
_COL_WIDTH_SIZE = 10
_COL_WIDTH_MEDIA_TYPE = 5


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser with ``--min-size-mb``
                                 and ``--output`` arguments.
    """
    parser = argparse.ArgumentParser(
        description="Export Apple Photos library metadata to CSV, sorted by file size."
    )
    parser.add_argument(
        "--min-size-mb",
        type=float,
        default=0.0,
        help="Only include items larger than this size in MB (default: include all)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output file path (default: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=SUPPORTED_FORMATS,
        default=DEFAULT_FORMAT,
        help=f"Output format (default: {DEFAULT_FORMAT})",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        default=False,
        help="Launch the web UI instead of exporting to a file",
    )
    return parser


def validate_output_path(output_path: str) -> Path:
    """Validate and prepare the output file path.

    Creates parent directories if they don't exist. Warns if an existing
    file will be overwritten. Checks that the destination has enough disk
    space for a reasonable CSV output.

    Args:
        output_path (str): Destination file path for the CSV.

    Returns:
        Path: The validated output path.

    Raises:
        SystemExit: If the parent directory cannot be created or there
                    is insufficient disk space.
    """
    path = Path(output_path)

    # Ensure parent directory exists
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Cannot create output directory {path.parent}: {e}", file=sys.stderr)
        sys.exit(_EXIT_CODE_ERROR)

    if path.exists():
        print(f"Note: overwriting existing file {path}", file=sys.stderr)

    # Rough disk space check — a large library (100k items) produces
    # roughly 15-20 MB of CSV, so 50 MB is a comfortable minimum
    min_free_bytes = _MIN_FREE_DISK_SPACE_MB * BYTES_PER_MB
    try:
        free_bytes = shutil.disk_usage(path.parent).free
    except OSError as e:
        print(
            f"Warning: could not check disk space for {path.parent}: {e}",
            file=sys.stderr,
        )
        return path
    if free_bytes < min_free_bytes:
        print(
            f"Insufficient disk space: {format_bytes(free_bytes)} free, "
            f"need at least {format_bytes(min_free_bytes)}",
            file=sys.stderr,
        )
        sys.exit(_EXIT_CODE_ERROR)

    return path


def print_summary(records: list[PhotoRecord], top_n: int = 10) -> None:
    """Print a summary report to stderr.

    Displays total item count, total size, and the largest items.

    Args:
        records (list[PhotoRecord]): Records to summarize, assumed pre-sorted
                                     by size descending.
        top_n (int): Number of largest items to display. Defaults to 10.
    """
    if not records:
        print("No items found.", file=sys.stderr)
        return

    total_bytes = sum(r.size_bytes for r in records)

    print(file=sys.stderr)
    print("=== Photos Library Report ===", file=sys.stderr)
    print(f"Total items: {len(records):,}", file=sys.stderr)
    print(f"Total size:  {format_bytes(total_bytes)}", file=sys.stderr)
    display_count = min(top_n, len(records))

    print(file=sys.stderr)
    print(f"Top {display_count} Largest Items:", file=sys.stderr)

    for i, record in enumerate(records[:display_count], start=1):
        print(
            f"  {i:>{_COL_WIDTH_RANK}}. {record.filename:<{_COL_WIDTH_FILENAME}}"
            f" {record.size:>{_COL_WIDTH_SIZE}}"
            f"   {record.media_type:<{_COL_WIDTH_MEDIA_TYPE}}  {record.icloud_status}",
            file=sys.stderr,
        )


def _start_web() -> None:
    """Import and start the web UI. Raises ImportError if Flask is not installed."""
    from iphoto_sizer.web import serve_web  # noqa: PLC0415

    serve_web()


def main() -> None:
    """Run the full export pipeline: load, extract, filter, sort, write, summarize."""
    try:
        _run()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(_EXIT_CODE_INTERRUPTED)


def _run() -> None:
    """Inner pipeline logic, separated so ``main()`` owns interrupt handling."""
    args = build_arg_parser().parse_args()

    if args.min_size_mb < 0:
        print("Error: --min-size-mb cannot be negative", file=sys.stderr)
        sys.exit(_EXIT_CODE_ERROR)

    if args.web:
        try:
            _start_web()
        except ImportError:
            print(
                "The --web flag requires the [web] extra.\n"
                'Install it with: pip install "iphoto-sizer[web]"',
                file=sys.stderr,
            )
            sys.exit(_EXIT_CODE_ERROR)
        return

    output_path = validate_output_path(args.output)
    db = load_photos_db()

    records, skipped = scan_library(db, min_size_mb=args.min_size_mb)
    if skipped:
        print(f"Skipped {skipped} item(s) due to errors.", file=sys.stderr)

    writer = FORMAT_WRITERS[args.format]
    writer(records, output_path)
    print(f"{args.format.upper()} written to {output_path}", file=sys.stderr)
    print_summary(records)
