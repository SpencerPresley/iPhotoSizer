# icloud-file-sorter

Exports metadata from your macOS Apple Photos library to CSV or JSON, sorted by file size (largest first). Useful for finding what's eating your iCloud storage.

Each record includes: filename, extension, media type (photo/video), size in bytes, human-readable size, creation date, UUID, and iCloud sync status (local vs cloud-only).

## Prerequisites

- macOS with the Photos app and a library present
- Python 3.11+
- Full Disk Access granted to your terminal (System Settings > Privacy & Security > Full Disk Access)

## Install

```bash
# Clone and install with uv
git clone <repo-url> && cd icloud-file-sorter
uv sync
```

Or install with pip:

```bash
pip install .
```

## Usage

After installing, a `photos-export` CLI command is available:

```bash
# Export everything to output/photos_report.csv
photos-export

# Only items larger than 100 MB
photos-export --min-size-mb 100

# Write to a specific path
photos-export -o ~/Desktop/large_files.csv

# Export as JSON instead of CSV
photos-export -f json -o ~/Desktop/photos.json

# Combine options
photos-export --min-size-mb 500 -f json -o ~/Desktop/big_ones.json
```

You can also run it as a module:

```bash
python -m icloud_file_sorter
```

## CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--min-size-mb` | Only include items at or above this size (MB) | `0` (all items) |
| `-o`, `--output` | Output file path | `output/photos_report.csv` |
| `-f`, `--format` | Output format: `csv` or `json` | `csv` |

## Output

**CSV columns / JSON fields:**

`filename`, `extension`, `media_type`, `size_bytes`, `size`, `creation_date`, `uuid`, `icloud_status`

- `size` is human-readable (e.g. `"150.23 MB"`, `"1.50 GB"`)
- `icloud_status` is `"local"` if the original file is on disk, `"cloud-only"` if it only exists in iCloud
- Records are sorted by `size_bytes` descending

A summary of total items, total size, and the 10 largest files is printed to stderr after export.

## Notes

- Initial library load takes 15-20 seconds on large libraries.
- Photos that fail to parse are skipped with a warning; they don't stop the export.
- The tool checks for at least 50 MB of free disk space before writing.
