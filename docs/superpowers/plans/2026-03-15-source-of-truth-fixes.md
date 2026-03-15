# Source of Truth Fixes

> **For agentic workers:** Each task is independent and can be dispatched to a subagent.

**Goal:** Eliminate multiple-source-of-truth issues found during codebase review. Five fixes, each self-contained.

---

## Task A: Extract scan pipeline to `core.py`

**Problem:** The photo processing pipeline (load DB → iterate photos → try/except → count skipped → filter → sort) is duplicated between `cli.py:213-233` and `web/routes.py:35-53`. Bug fixes in one path will be missed in the other.

**Files:**
- Modify: `src/iphoto_sizer/core.py` — add `scan_library()` function
- Modify: `src/iphoto_sizer/cli.py:213-233` — replace inline pipeline with `scan_library()` call
- Modify: `src/iphoto_sizer/web/routes.py:35-53` — replace inline pipeline with `scan_library()` call
- Modify: `tests/test_core.py` — add tests for `scan_library()`
- Modify: `src/iphoto_sizer/__init__.py` — export `scan_library`

**What to build:**

In `core.py`, add:

```python
def scan_library(
    db: osxphotos.PhotosDB,
    min_size_mb: float = 0,
) -> tuple[list[PhotoRecord], int]:
    """Scan the Photos library and return sorted records with skip count.

    Args:
        db: The loaded Photos database.
        min_size_mb: Minimum file size filter in MB. 0 includes all.

    Returns:
        A tuple of (sorted records descending by size, number of skipped photos).
    """
    skipped = 0
    records: list[PhotoRecord] = []
    for photo in db.photos():
        try:
            records.append(photo_to_record(photo))
        except Exception:
            skipped += 1

    if min_size_mb > 0:
        records = apply_filters(records, min_size_bytes=min_size_mb * BYTES_PER_MB)

    records.sort(key=lambda r: r.size_bytes, reverse=True)
    return records, skipped
```

In `cli.py` `_run()`, replace lines 213-233 (the `skipped = 0` through `records.sort(...)`) with:

```python
from iphoto_sizer.core import scan_library

records, skipped = scan_library(db, min_size_mb=args.min_size_mb)
```

Keep the skipped warning print after the call:
```python
if skipped:
    print(f"Skipped {skipped} item(s) due to errors.", file=sys.stderr)
```

Note: the CLI currently has extra logic to print the UUID of each skipped photo (lines 222-225). This per-photo warning is lost when consolidating. Decide whether to:
- (a) Drop the per-photo UUID logging (simplifies, web route already does this)
- (b) Accept a callback parameter for skip reporting
- (c) Log to stderr inside `scan_library()` directly

Recommendation: (a) — the skipped count is sufficient. The per-photo UUID was a nice-to-have but not critical.

In `web/routes.py` `scan()`, replace lines 35-53 with:

```python
from iphoto_sizer.core import scan_library

records, skipped = scan_library(db, min_size_mb=min_size_mb)
```

**Tests:** Add to `test_core.py`:

```python
class TestScanLibrary:
    def test_returns_sorted_records(self):
        mock_db = MagicMock()
        mock_db.photos.return_value = [
            _fake_photo(original_filename="small.jpg", original_filesize=100),
            _fake_photo(original_filename="big.jpg", original_filesize=999_999),
        ]
        records, skipped = scan_library(mock_db)
        assert records[0].filename == "big.jpg"
        assert skipped == 0

    def test_counts_skipped_photos(self):
        mock_db = MagicMock()
        bad = SimpleNamespace(
            original_filename=None, original_filesize="bad",
            ismovie=False, date=None, uuid="X", ismissing=False,
        )
        good = _fake_photo()
        mock_db.photos.return_value = [bad, good]
        records, skipped = scan_library(mock_db)
        assert len(records) == 1
        assert skipped == 1

    def test_applies_min_size_filter(self):
        mock_db = MagicMock()
        mock_db.photos.return_value = [
            _fake_photo(original_filesize=100),
            _fake_photo(original_filename="big.mov", original_filesize=500_000_000),
        ]
        records, skipped = scan_library(mock_db, min_size_mb=100)
        assert len(records) == 1
        assert records[0].filename == "big.mov"
```

**Commit:** `refactor: extract scan pipeline to core.scan_library()`

---

## Task B: Centralize default filename stem and default format

**Problem:**
- `"photos_report"` is hardcoded in 4 places: `models.py:14`, `web/routes.py:81`, `web/templates/index.html:164`, `web/static/app.js:474`
- `"csv"` as default format is hardcoded in 4 places: `cli.py:78`, `web/routes.py:80`, `web/static/app.js:419`, `web/templates/index.html:157`

**Files:**
- Modify: `src/iphoto_sizer/models.py:14` — add `DEFAULT_OUTPUT_STEM = "photos_report"` and `DEFAULT_FORMAT: OutputFormat = "csv"`
- Modify: `src/iphoto_sizer/cli.py:78` — use `DEFAULT_FORMAT` for argparse default
- Modify: `src/iphoto_sizer/web/routes.py:80-81` — use `DEFAULT_FORMAT` and `DEFAULT_OUTPUT_STEM` for fallbacks
- Modify: `src/iphoto_sizer/web/templates/index.html:157,164` — inject defaults via Jinja2 template variables
- Modify: `src/iphoto_sizer/web/__init__.py` or `web/routes.py` — pass defaults to template context
- Modify: `src/iphoto_sizer/__init__.py` — export new constants

**What to build:**

In `models.py`, change line 14 and add:

```python
DEFAULT_OUTPUT_STEM = "photos_report"
DEFAULT_OUTPUT_FILE = f"{DEFAULT_OUTPUT_STEM}.csv"
DEFAULT_FORMAT: OutputFormat = "csv"
```

In `cli.py`, replace `default="csv"` with `DEFAULT_FORMAT`:
```python
from iphoto_sizer.models import DEFAULT_FORMAT
# ...
parser.add_argument("--format", ..., default=DEFAULT_FORMAT, ...)
```

In `web/routes.py`, replace hardcoded defaults:
```python
from iphoto_sizer.models import DEFAULT_FORMAT, DEFAULT_OUTPUT_STEM
# ...
fmt = body.get("format", DEFAULT_FORMAT)
filename = body.get("filename", DEFAULT_OUTPUT_STEM)
```

In `web/routes.py` `index()`, pass template context:
```python
@bp.route("/")
def index():
    return render_template("index.html",
        default_filename=DEFAULT_OUTPUT_STEM,
        default_format=DEFAULT_FORMAT,
    )
```

In `index.html`, use Jinja2 variables:
```html
<input ... value="{{ default_filename }}" placeholder="{{ default_filename }}">
```

The JS fallback in `app.js:474` (`exportFilename.value || "photos_report"`) can stay — it reads the input's value which is already set by the template. The `selectedFormat` default in JS can also stay since it reads the `selected` class from the template-rendered buttons.

**Commit:** `refactor: centralize default filename and format constants`

---

## Task C: Extract test factories to conftest.py

**Problem:**
- `_fake_photo()` is copy-pasted in 3 files: `tests/test_core.py:13-24`, `tests/test_cli.py:195-208`, `tests/test_web/test_routes.py:13-23`
- `_make_record()` is copy-pasted in 2 files: `tests/test_cli.py:21-34`, `tests/test_writers.py:11-24`
- `_fake_photo_record_dict()` in `tests/test_web/test_routes.py:150-160` duplicates the same defaults

**Files:**
- Create: `tests/conftest.py` — shared fixtures
- Modify: `tests/test_core.py` — remove local `_fake_photo()`, import from conftest
- Modify: `tests/test_cli.py` — remove local `_fake_photo()` and `_make_record()`, import from conftest
- Modify: `tests/test_writers.py` — remove local `_make_record()`, import from conftest
- Modify: `tests/test_web/test_routes.py` — remove local `_fake_photo()` and `_fake_photo_record_dict()`, import from conftest

**What to build:**

Create `tests/conftest.py`:

```python
"""Shared test factories and fixtures."""

from datetime import UTC, datetime
from types import SimpleNamespace

from iphoto_sizer.models import PhotoRecord


def make_fake_photo(**overrides: object) -> SimpleNamespace:
    """Create a fake osxphotos.PhotoInfo-like object with sensible defaults."""
    defaults = {
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
    """Create a PhotoRecord with sensible defaults, overriding specific fields."""
    defaults = {
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


def make_record_dict(**overrides: object) -> dict:
    """Create a PhotoRecord-shaped dict for API testing."""
    record = make_record(**overrides)
    return record.model_dump()
```

Then in each test file, replace the local helper with an import:
- `from tests.conftest import make_fake_photo, make_record, make_record_dict`
- Or use them as pytest fixtures if preferred

Update all call sites:
- `_fake_photo(...)` → `make_fake_photo(...)`
- `_make_record(...)` → `make_record(...)`
- `_fake_photo_record_dict()` → `make_record_dict()`

**Commit:** `refactor: extract test factories to shared conftest.py`

---

## Task D: Add media type and iCloud status constants

**Problem:**
- `"photo"` and `"video"` are string literals in: `models.py:43`, `core.py:76`, `web/routes.py:56`, `app.js:153,365,538-547`
- `"local"` and `"cloud-only"` are string literals in: `models.py:48`, `core.py:84`, `app.js:372`

**Files:**
- Modify: `src/iphoto_sizer/models.py` — add constants
- Modify: `src/iphoto_sizer/core.py:76,84` — use constants
- Modify: `src/iphoto_sizer/web/routes.py:56` — use constant
- Modify: `src/iphoto_sizer/__init__.py` — export new constants

**What to build:**

In `models.py`, add after the existing constants:

```python
MEDIA_TYPE_PHOTO = "photo"
MEDIA_TYPE_VIDEO = "video"
ICLOUD_STATUS_LOCAL = "local"
ICLOUD_STATUS_CLOUD_ONLY = "cloud-only"
```

Keep the `Literal` type annotations — they stay as the type constraint. The constants are for use in code that produces these values.

In `core.py:76`:
```python
# Before:
media_type="video" if photo.ismovie else "photo",
# After:
media_type=MEDIA_TYPE_VIDEO if photo.ismovie else MEDIA_TYPE_PHOTO,
```

In `core.py:84`:
```python
# Before:
icloud_status="cloud-only" if photo.ismissing else "local",
# After:
icloud_status=ICLOUD_STATUS_CLOUD_ONLY if photo.ismissing else ICLOUD_STATUS_LOCAL,
```

In `web/routes.py:56`:
```python
# Before:
video_count = sum(1 for r in records if r.media_type == "video")
# After:
video_count = sum(1 for r in records if r.media_type == MEDIA_TYPE_VIDEO)
```

The JS side (`app.js`) keeps its own string literals — this is inherent to the client/server boundary and acceptable. The Python side is now single-sourced.

**Commit:** `refactor: add named constants for media type and iCloud status values`

---

## Task E: Add `_EXIT_CODE_ERROR` constant

**Problem:** `sys.exit(1)` appears as a bare literal in 5 places across `core.py` and `cli.py`. The interrupt exit code has a named constant (`_EXIT_CODE_INTERRUPTED = 130`) but the general error code doesn't.

**Files:**
- Modify: `src/iphoto_sizer/cli.py` — add `_EXIT_CODE_ERROR = 1`, replace all `sys.exit(1)` calls
- Modify: `src/iphoto_sizer/core.py:114` — import and use `_EXIT_CODE_ERROR`

**What to build:**

In `cli.py`, add next to the existing `_EXIT_CODE_INTERRUPTED`:

```python
_EXIT_CODE_ERROR = 1
_EXIT_CODE_INTERRUPTED = 130
```

Replace all `sys.exit(1)` in `cli.py` with `sys.exit(_EXIT_CODE_ERROR)`:
- Line 113 (validate_output_path mkdir failure)
- Line 135 (validate_output_path disk space)
- Line 197 (negative --min-size-mb)
- Line 207 (missing Flask)

In `core.py:114`, the `sys.exit(1)` in `load_photos_db()` — either:
- Import `_EXIT_CODE_ERROR` from `cli` (creates a circular-ish dependency, not ideal)
- Define a separate `_EXIT_CODE_ERROR = 1` in `core.py`
- Accept the bare `1` in `core.py` since it's a single occurrence in a different module

Recommendation: Define `_EXIT_CODE_ERROR = 1` in `core.py` separately. It's a trivial constant and keeping it local avoids an import dependency from core → cli.

**Commit:** `refactor: add named constant for error exit code`
