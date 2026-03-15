"""Route handlers for the web UI."""

from flask import Blueprint, render_template

bp = Blueprint("web", __name__)


@bp.route("/")
def index() -> str:
    """Serve the single-page app shell."""
    return render_template("index.html")
