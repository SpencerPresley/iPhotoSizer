# Web UI Design Spec

## Overview

Add an optional web-based interface to iphoto-sizer via a `--web` flag. The web UI provides a browsable, sortable, filterable view of Photos library metadata with the ability to open items in Photos.app and export results to disk. It is a standalone mode — CLI-only flags (`-o`, `-f`) are ignored when `--web` is active.

## Architecture

### Package Structure

```
src/iphoto_sizer/web/
    __init__.py       # Flask app factory, startup logic
    routes.py         # Route handlers
    templates/        # Jinja2 HTML templates
    static/           # CSS/JS assets
```

The web module imports existing business logic — no duplication:

- `core.py` — `load_photos_db()`, `photo_to_record()`, `apply_filters()`
- `models.py` — `PhotoRecord`, `SUPPORTED_FORMATS`, `format_bytes()`
- `writers.py` — `write_csv()`, `write_json()` (reused for export)

### Optional Dependency

Flask is an optional extra. Core CLI functionality has no Flask dependency.

```toml
[project.optional-dependencies]
web = ["flask>=3.0"]
```

If `--web` is passed without Flask installed, the CLI prints an actionable error and exits:

```
The --web flag requires the [web] extra.
Install it with: pip install iphoto-sizer[web]
```

## CLI Changes

### New Flag

`--web` — starts the web UI instead of the standard export pipeline. When `--web` is active, `-o`, `-f`, and `--min-size-mb` are silently ignored (these are controlled from the web UI instead). No warning or error is emitted — the flags are simply not read.

### No New Flags

`--no-file` is not needed. File saving is handled entirely within the web UI via an export button. The existing CLI flags (`-o`, `-f`, `--min-size-mb`) remain unchanged for the non-web path.

## User Flow

### Entry

```bash
iphoto-sizer --web
```

1. CLI checks Flask is installed (graceful error if not).
2. Flask dev server starts on `127.0.0.1`. The actual OS-assigned port is read from the bound server socket after binding (not from Flask config, which would show port 0).
3. Browser opens automatically via `webbrowser.open()` using the actual bound port.
4. Server runs until Ctrl+C.

### Landing Page

Two options presented to the user:

- **Run new scan** — triggers a library scan from the web UI.
- **Open existing report** — file picker / drag-and-drop to load a previously exported JSON file. The file is parsed entirely client-side with JavaScript (FileReader API) — no server upload needed. The parsed records are then used to render the same results UI. Note: since the data never reaches the server, the "Open in Photos" action will still work (it only needs the UUID sent per-click), but "Export" will send the records to the server at that time.

### Scan Flow

1. User clicks "Run new scan" (optionally sets a minimum size filter via a form field).
2. UI shows a spinner with "Scanning library...".
3. `POST /scan` is sent with a JSON body. The request blocks synchronously for the duration of the scan (typically 5-20 seconds). This is acceptable for v1 — the library is local, the server has one user, and the spinner provides feedback. If scan times become problematic in practice, a polling/async pattern can be added later.
4. Server runs the export pipeline: `load_photos_db()` → `photo_to_record()` for each item → `apply_filters()` → sort by `size_bytes` descending.
5. Response JSON is returned and rendered in the results UI.

### Results UI

**Summary stats bar** at the top:

- Total items count
- Total size (human-readable)
- Video count / Photo count breakdown
- Skipped items count (if any)

**Main content area:**

- Browsable, sortable, filterable view of all records.
- The presentation format (cards, table, hybrid, etc.) will be designed during implementation using the `frontend-design` skill. The spec intentionally does not prescribe a specific UI pattern — the goal is a well-designed interface, not a raw data dump.
- Each item displays: filename, extension, media type, size, creation date, iCloud status.
- UUID is available but not necessarily prominent — it is metadata for the "Open in Photos" action.

**Available fields per record:**

| Field | Display |
|---|---|
| `filename` | Primary identifier |
| `extension` | File type context |
| `media_type` | "photo" or "video" |
| `size` | Human-readable (e.g. "1.50 GB") |
| `size_bytes` | Available for sorting, not necessarily displayed |
| `creation_date` | Timestamp |
| `uuid` | Used for Photos.app integration |
| `icloud_status` | "local" or "cloud-only" |

### Export (Save to File)

An "Export" button in the results UI opens a dropdown/dialog with:

- **Format selection** — dynamically populated from `SUPPORTED_FORMATS` (currently `csv`, `json`). Adding a new writer to the codebase automatically makes it available here. Includes an "All formats" option.
- **Filename field** — sensible default (e.g. `photos_report`). No directory picker — files are written to the current working directory (the directory from which `iphoto-sizer --web` was launched).
- **Save button** — triggers `POST /export`, server writes the file, response confirms the full path.

### Photos.app Integration

Clicking an item in the results UI triggers a request to open it in Photos.app.

- Server endpoint receives the UUID.
- `photoscript` is imported defensively with a try/except. It is an indirect dependency via `osxphotos`, but transitive dependencies can be fragile. If the import fails, the endpoint returns an error and the UI disables the "Open in Photos" functionality with a message.
- `photoscript.Photo(uuid).spotlight()` opens/highlights the photo. Photos.app will be launched automatically if not already running.
- This feature is marked as **experimental** since Apple provides no stable API for it. The `spotlight()` method uses AppleScript internally and may not work reliably across all macOS versions.

## API Endpoints

### `GET /`

Serve the landing page.

### `POST /scan`

Run the export pipeline and return results.

**Request body (JSON):**
```json
{
  "min_size_mb": 100.0
}
```
All fields optional. Omitting `min_size_mb` or setting it to `0` includes all items.

**Response body (JSON):**
```json
{
  "records": [
    {
      "filename": "IMG_001.mov",
      "extension": "mov",
      "media_type": "video",
      "size_bytes": 1500000000,
      "size": "1.40 GB",
      "creation_date": "2024-06-15 14:30:00",
      "uuid": "ABC-123-DEF",
      "icloud_status": "local"
    }
  ],
  "skipped_count": 2,
  "total_count": 24567,
  "total_size_bytes": 367521402880,
  "total_size": "342.15 GB",
  "video_count": 1234,
  "photo_count": 23333
}
```

### `POST /export`

Save records to disk in the requested format(s).

**Request body (JSON):**
```json
{
  "records": [ ... ],
  "format": "csv",
  "filename": "photos_report"
}
```
`format` is one of the values from `SUPPORTED_FORMATS`, or `"all"` to write every supported format. `filename` is the base name without extension (extension is appended based on format).

**Response body (JSON):**
```json
{
  "paths": ["/Users/spencer/photos_report.csv"]
}
```
Or on error:
```json
{
  "error": "Permission denied: /readonly/photos_report.csv"
}
```

### `POST /open/<uuid>`

Open a photo in Photos.app.

**Response body (JSON):**
```json
{
  "success": true
}
```
Or on error:
```json
{
  "success": false,
  "error": "photoscript not available"
}
```

## UI Architecture

The UI is a **single-page app with client-side JavaScript transitions**, not server-rendered multi-page navigation. Flask serves one HTML shell (via Jinja2) that includes the JS and CSS assets. All state transitions (landing → spinner → results) happen client-side. API calls use `fetch()`.

This means:
- `GET /` returns the full HTML shell (single Jinja2 template or a minimal shell with static assets).
- All other endpoints return JSON.
- The frontend JS handles rendering, transitions, and user interactions.

## Server Lifecycle

- Flask dev server bound to `127.0.0.1` only (not exposed to network).
- Port 0 passed to Flask, actual port read from the bound server socket after startup.
- Browser opened automatically via `threading.Timer(0.5, webbrowser.open, ...)` using the actual port.
- `Ctrl+C` triggers clean shutdown.
- Stderr output: `"Web UI running at http://localhost:{port} — press Ctrl+C to stop"`.

## Error Handling

- **Flask not installed:** Actionable error message with install command, `sys.exit(1)`.
- **Photos library not accessible:** Same Full Disk Access error as CLI path, returned as JSON error (`{"error": "..."}`) to the UI which displays it.
- **Individual photo failures during scan:** Skipped with warnings (same as CLI). The `skipped_count` is included in the scan response and shown in the UI.
- **photoscript import failure:** `POST /open/<uuid>` returns `{"success": false, "error": "photoscript not available"}`. The UI disables or hides the "Open in Photos" button.
- **photoscript.spotlight() failure:** Returns `{"success": false, "error": "..."}`. UI shows a non-blocking notification.
- **Export write failure:** Returns `{"error": "..."}` with the OS error message.

## Testing Strategy

- **Unit tests:** Route handlers with Flask test client. Mock `load_photos_db()` and `photoscript`.
- **Template tests:** Verify the HTML shell renders without errors.
- **API contract tests:** Verify request/response schemas for `/scan`, `/export`, `/open/<uuid>`.
- **Integration tests (marked):** `@pytest.mark.integration` — test against a real Photos library. Only run when explicitly requested.

## Out of Scope

- Authentication / multi-user access (localhost only).
- Photo thumbnails or previews (would require downloading/accessing the actual image files).
- Batch operations (delete, export photos themselves).
- Persistent server / daemon mode.
- Async/polling pattern for long scans (acceptable to block synchronously for v1).
