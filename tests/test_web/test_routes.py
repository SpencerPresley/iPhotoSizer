"""Tests for iphoto_sizer.web routes."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from iphoto_sizer.web import create_app
from tests.conftest import make_fake_photo, make_record_dict


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
        mock_db.photos.return_value = [make_fake_photo()]
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
            make_fake_photo(original_filesize=100),
            make_fake_photo(original_filename="big.mov", original_filesize=500_000_000),
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
            make_fake_photo(original_filename="small.jpg", original_filesize=100),
            make_fake_photo(original_filename="big.jpg", original_filesize=999_999),
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
            make_fake_photo(ismovie=False, original_filesize=100),
            make_fake_photo(ismovie=True, original_filesize=200),
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


class TestExportEndpoint:
    def test_export_csv(self, tmp_path: Path) -> None:
        app = create_app()
        app.config["EXPORT_DIR"] = str(tmp_path)
        client = app.test_client()
        records = [make_record_dict()]
        response = client.post("/export", json={
            "records": records,
            "format": "csv",
            "filename": "test_report",
        })
        assert response.status_code == 200
        data = response.get_json()
        assert "paths" in data
        assert any("test_report.csv" in p for p in data["paths"])

    def test_export_json(self, tmp_path: Path) -> None:
        app = create_app()
        app.config["EXPORT_DIR"] = str(tmp_path)
        client = app.test_client()
        records = [make_record_dict()]
        response = client.post("/export", json={
            "records": records,
            "format": "json",
            "filename": "test_report",
        })
        data = response.get_json()
        assert any("test_report.json" in p for p in data["paths"])

    def test_export_all_formats(self, tmp_path: Path) -> None:
        app = create_app()
        app.config["EXPORT_DIR"] = str(tmp_path)
        client = app.test_client()
        records = [make_record_dict()]
        response = client.post("/export", json={
            "records": records,
            "format": "all",
            "filename": "test_report",
        })
        data = response.get_json()
        assert len(data["paths"]) == 2  # csv and json

    def test_export_invalid_format(self) -> None:
        app = create_app()
        client = app.test_client()
        response = client.post("/export", json={
            "records": [],
            "format": "xml",
            "filename": "test",
        })
        assert response.status_code == 400

    def test_export_empty_records(self, tmp_path: Path) -> None:
        app = create_app()
        app.config["EXPORT_DIR"] = str(tmp_path)
        client = app.test_client()
        response = client.post("/export", json={
            "records": [],
            "format": "csv",
            "filename": "empty",
        })
        assert response.status_code == 200

    def test_export_defaults(self, tmp_path: Path) -> None:
        """Missing format/filename fields use defaults."""
        app = create_app()
        app.config["EXPORT_DIR"] = str(tmp_path)
        client = app.test_client()
        response = client.post("/export", json={
            "records": [make_record_dict()],
        })
        assert response.status_code == 200
        data = response.get_json()
        assert any("photos_report.csv" in p for p in data["paths"])


class TestFormatsEndpoint:
    def test_returns_supported_formats(self):
        app = create_app()
        client = app.test_client()
        response = client.get("/api/formats")
        assert response.status_code == 200
        data = response.get_json()
        assert "csv" in data["formats"]
        assert "json" in data["formats"]


class TestOpenEndpoint:
    def test_open_photo_success(self) -> None:
        app = create_app()
        client = app.test_client()
        with patch("iphoto_sizer.web.routes._open_in_photos") as mock_open:
            mock_open.return_value = None
            response = client.post("/open/ABC-123-DEF")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_open_photo_failure(self) -> None:
        app = create_app()
        client = app.test_client()
        with patch("iphoto_sizer.web.routes._open_in_photos", side_effect=Exception("not found")):
            response = client.post("/open/ABC-123-DEF")
        data = response.get_json()
        assert data["success"] is False
        assert "error" in data


class TestFullPipeline:
    def test_scan_then_export(self, tmp_path: Path) -> None:
        """Full flow: scan the library, then export the results."""
        app = create_app()
        app.config["EXPORT_DIR"] = str(tmp_path)
        client = app.test_client()

        mock_db = MagicMock()
        mock_db.photos.return_value = [
            make_fake_photo(original_filename="big.mov", original_filesize=1_000_000, ismovie=True),
            make_fake_photo(original_filename="small.jpg", original_filesize=100),
        ]

        # Step 1: Scan
        with patch("iphoto_sizer.web.routes.load_photos_db", return_value=mock_db):
            scan_response = client.post("/scan", json={})
        assert scan_response.status_code == 200
        scan_data = scan_response.get_json()
        assert scan_data["total_count"] == 2

        # Step 2: Export the scan results
        export_response = client.post("/export", json={
            "records": scan_data["records"],
            "format": "csv",
            "filename": "test_export",
        })
        assert export_response.status_code == 200
        paths = export_response.get_json()["paths"]
        assert len(paths) == 1
        assert Path(paths[0]).exists()

    def test_open_existing_then_export(self, tmp_path: Path) -> None:
        """Simulate the 'Open existing report' flow: records come from client, not from /scan."""
        app = create_app()
        app.config["EXPORT_DIR"] = str(tmp_path)
        client = app.test_client()

        # Records loaded client-side (not from /scan), sent directly to /export
        client_records = [
            make_record_dict(),
            {
                "filename": "video.mov",
                "extension": "mov",
                "media_type": "video",
                "size_bytes": 500_000,
                "size": "0.48 MB",
                "creation_date": "2024-03-01 10:00:00",
                "uuid": "XYZ-789",
                "icloud_status": "cloud-only",
            },
        ]

        response = client.post("/export", json={
            "records": client_records,
            "format": "json",
            "filename": "reopened_report",
        })
        assert response.status_code == 200
        paths = response.get_json()["paths"]
        assert len(paths) == 1
        assert Path(paths[0]).exists()
