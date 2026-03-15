"""Route handlers for the web UI."""

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from flask import Blueprint, current_app, jsonify, render_template, request
from flask.typing import ResponseReturnValue

from iphoto_sizer.core import apply_filters, load_photos_db, photo_to_record
from iphoto_sizer.models import BYTES_PER_MB, SUPPORTED_FORMATS, PhotoRecord, format_bytes
from iphoto_sizer.writers import FORMAT_WRITERS

_PHOTOSCRIPT_AVAILABLE: bool = importlib.util.find_spec("photoscript") is not None
_photoscript: ModuleType | None = None
if _PHOTOSCRIPT_AVAILABLE:
    import photoscript

    _photoscript = photoscript

bp = Blueprint("web", __name__)


@bp.route("/")
def index() -> str:
    """Serve the single-page app shell."""
    return render_template("index.html")


@bp.route("/scan", methods=["POST"])
def scan() -> ResponseReturnValue:
    """Run the export pipeline and return results as JSON."""
    try:
        db = load_photos_db()
    except SystemExit:
        return jsonify({"error": "Could not open Photos library. Check Full Disk Access."}), 500

    body: dict[str, Any] = request.get_json(silent=True) or {}
    min_size_mb: float = float(body.get("min_size_mb", 0.0))

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

    total_size_bytes = sum(r.size_bytes for r in records)
    video_count = sum(1 for r in records if r.media_type == "video")
    photo_count = len(records) - video_count

    return jsonify({
        "records": [r.model_dump() for r in records],
        "skipped_count": skipped,
        "total_count": len(records),
        "total_size_bytes": total_size_bytes,
        "total_size": format_bytes(total_size_bytes),
        "video_count": video_count,
        "photo_count": photo_count,
    })


@bp.route("/api/formats")
def formats() -> ResponseReturnValue:
    """Return the list of supported export formats."""
    return jsonify({"formats": list(SUPPORTED_FORMATS)})


@bp.route("/export", methods=["POST"])
def export() -> ResponseReturnValue:
    """Save records to disk in the requested format(s)."""
    body: dict[str, Any] = request.get_json(silent=True) or {}
    fmt: str = str(body.get("format", "csv"))
    filename: str = str(body.get("filename", "photos_report"))
    raw_records: list[dict[str, Any]] = body.get("records", [])

    if fmt != "all" and fmt not in SUPPORTED_FORMATS:
        return jsonify({"error": f"Unsupported format: {fmt}"}), 400

    records = [PhotoRecord(**r) for r in raw_records]

    formats = list(SUPPORTED_FORMATS) if fmt == "all" else [fmt]
    export_dir = Path(cast("str", current_app.config.get("EXPORT_DIR", ".")))
    paths: list[str] = []

    try:
        for f in formats:
            output_path = export_dir / f"{filename}.{f}"
            writer = FORMAT_WRITERS[f]
            writer(records, output_path)
            paths.append(str(output_path.resolve()))
    except OSError as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"paths": paths})


def _open_in_photos(uuid: str) -> None:
    """Open a photo in Photos.app via photoscript. Raises if it fails."""
    if _photoscript is None:
        msg = "photoscript is not installed"
        raise RuntimeError(msg)
    photo = _photoscript.Photo(uuid)
    photo.spotlight()


@bp.route("/open/<uuid>", methods=["POST"])
def open_photo(uuid: str) -> ResponseReturnValue:
    """Open a photo in Photos.app."""
    if not _PHOTOSCRIPT_AVAILABLE:
        return jsonify({"success": False, "error": "photoscript not available"})

    try:
        _open_in_photos(uuid)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

    return jsonify({"success": True})
