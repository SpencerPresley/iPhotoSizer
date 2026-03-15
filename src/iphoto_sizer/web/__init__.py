"""Flask web UI for iphoto-sizer."""

import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["EXPORT_DIR"] = str(Path.cwd())

    from iphoto_sizer.web.routes import bp  # noqa: PLC0415

    app.register_blueprint(bp)

    return app


def serve_web() -> None:
    """Start the Flask dev server and open the browser."""
    app = create_app()

    # Use port 0 to let the OS assign a free port.
    # Flask's run() doesn't easily expose the bound port before blocking,
    # so we use Werkzeug's server directly.
    from werkzeug.serving import make_server  # noqa: PLC0415

    server = make_server("127.0.0.1", 0, app)
    port = server.socket.getsockname()[1]

    url = f"http://localhost:{port}"
    print(f"Web UI running at {url} — press Ctrl+C to stop", file=sys.stderr)

    timer = threading.Timer(0.5, webbrowser.open, args=[url])
    timer.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        timer.cancel()
        server.shutdown()
        print("\nServer stopped.", file=sys.stderr)
