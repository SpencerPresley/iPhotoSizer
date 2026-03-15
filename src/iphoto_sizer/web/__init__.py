"""Flask web UI for iphoto-sizer."""

from pathlib import Path

from flask import Flask


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["EXPORT_DIR"] = str(Path.cwd())

    from iphoto_sizer.web.routes import bp  # noqa: PLC0415

    app.register_blueprint(bp)

    return app
