"""Route handlers for the web UI."""

from typing import Any

from flask import Blueprint, jsonify, render_template, request
from flask.typing import ResponseReturnValue

from iphoto_sizer.core import apply_filters, load_photos_db, photo_to_record
from iphoto_sizer.models import BYTES_PER_MB, PhotoRecord, format_bytes

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
