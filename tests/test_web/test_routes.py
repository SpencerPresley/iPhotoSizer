"""Tests for iphoto_sizer.web routes."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from iphoto_sizer.web import create_app


def _fake_photo(**overrides: object) -> SimpleNamespace:
    defaults = {
        "original_filename": "IMG_001.jpg",
        "original_filesize": 5_000_000,
        "ismovie": False,
        "date": datetime(2024, 6, 15, 14, 30, 0, tzinfo=UTC),
        "uuid": "ABC-123",
        "ismissing": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


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

    def test_serve_web_prints_url_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Verify the URL with actual port is printed to stderr."""
        mock_server = self._mock_make_server()
        with (
            patch("iphoto_sizer.web.webbrowser"),
            patch("werkzeug.serving.make_server", return_value=mock_server),
        ):
            from iphoto_sizer.web import serve_web

            serve_web()
        stderr = capsys.readouterr().err
        assert "Web UI running at http://localhost:8501" in stderr


class TestScanEndpoint:
    def test_scan_returns_json(self) -> None:
        app = create_app()
        client = app.test_client()
        mock_db = MagicMock()
        mock_db.photos.return_value = [_fake_photo()]
        with patch("iphoto_sizer.web.routes.load_photos_db", return_value=mock_db):
            response = client.post("/scan", json={})
        assert response.status_code == 200
        data = response.get_json()
        assert "records" in data
        assert "total_count" in data
        assert "skipped_count" in data

    def test_scan_with_min_size_filter(self) -> None:
        app = create_app()
        client = app.test_client()
        mock_db = MagicMock()
        mock_db.photos.return_value = [
            _fake_photo(original_filesize=100),
            _fake_photo(original_filename="big.mov", original_filesize=500_000_000),
        ]
        with patch("iphoto_sizer.web.routes.load_photos_db", return_value=mock_db):
            response = client.post("/scan", json={"min_size_mb": 100})
        data = response.get_json()
        assert data["total_count"] == 1

    def test_scan_returns_sorted_descending(self) -> None:
        app = create_app()
        client = app.test_client()
        mock_db = MagicMock()
        mock_db.photos.return_value = [
            _fake_photo(original_filename="small.jpg", original_filesize=100),
            _fake_photo(original_filename="big.jpg", original_filesize=999_999),
        ]
        with patch("iphoto_sizer.web.routes.load_photos_db", return_value=mock_db):
            response = client.post("/scan", json={})
        records = response.get_json()["records"]
        assert records[0]["filename"] == "big.jpg"

    def test_scan_includes_summary_stats(self) -> None:
        app = create_app()
        client = app.test_client()
        mock_db = MagicMock()
        mock_db.photos.return_value = [
            _fake_photo(ismovie=False, original_filesize=100),
            _fake_photo(ismovie=True, original_filesize=200),
        ]
        with patch("iphoto_sizer.web.routes.load_photos_db", return_value=mock_db):
            response = client.post("/scan", json={})
        data = response.get_json()
        assert data["photo_count"] == 1
        assert data["video_count"] == 1
        assert data["total_size_bytes"] == 300
        assert "total_size" in data

    def test_scan_handles_db_failure(self) -> None:
        app = create_app()
        client = app.test_client()
        with patch("iphoto_sizer.web.routes.load_photos_db", side_effect=SystemExit(1)):
            response = client.post("/scan", json={})
        assert response.status_code == 500
