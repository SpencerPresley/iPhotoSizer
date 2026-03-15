"""Tests for iphoto_sizer.web routes."""

from pathlib import Path

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
