"""Tests for iphoto_sizer.web routes."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from iphoto_sizer.web import create_app


class TestAppFactory:
    def test_create_app_returns_flask_app(self):
        app = create_app()
        assert app is not None
        assert app.name == "iphoto_sizer.web"

    def test_app_has_index_route(self):
        app = create_app()
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert "/" in rules

    def test_export_dir_defaults_to_cwd(self):
        app = create_app()
        assert app.config["EXPORT_DIR"] == str(Path.cwd())

    def test_index_returns_html(self):
        app = create_app()
        client = app.test_client()
        response = client.get("/")
        assert response.status_code == 200
        assert b"iphoto-sizer" in response.data


class TestServeWeb:
    def _mock_make_server(self) -> MagicMock:
        """Create a mock make_server that returns a controllable server."""
        mock_server = MagicMock()
        mock_server.socket.getsockname.return_value = ("127.0.0.1", 8501)
        # Make serve_forever raise KeyboardInterrupt to exit immediately
        mock_server.serve_forever.side_effect = KeyboardInterrupt
        return mock_server

    def test_serve_web_binds_to_localhost(self) -> None:
        """Verify serve_web binds to 127.0.0.1."""
        mock_server = self._mock_make_server()
        with (
            patch("iphoto_sizer.web.webbrowser"),
            patch("werkzeug.serving.make_server", return_value=mock_server) as mock_make,
        ):
            from iphoto_sizer.web import serve_web

            serve_web()
        mock_make.assert_called_once()
        assert mock_make.call_args[0][0] == "127.0.0.1"
        assert mock_make.call_args[0][1] == 0  # port 0 for auto-assign

    def test_serve_web_prints_url_to_stderr(self, capsys: object) -> None:
        """Verify the URL with actual port is printed to stderr."""
        mock_server = self._mock_make_server()
        with (
            patch("iphoto_sizer.web.webbrowser"),
            patch("werkzeug.serving.make_server", return_value=mock_server),
        ):
            from iphoto_sizer.web import serve_web

            serve_web()
        stderr = capsys.readouterr().err  # type: ignore[union-attr]
        assert "Web UI running at http://localhost:8501" in stderr
