"""Tests for iphoto_sizer.cli."""

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from iphoto_sizer.cli import (
    _run,
    build_arg_parser,
    main,
    print_summary,
    validate_output_path,
)
from iphoto_sizer.models import DEFAULT_OUTPUT_FILE, SUPPORTED_FORMATS, PhotoRecord


def _make_record(**overrides: object) -> PhotoRecord:
    """Create a PhotoRecord with sensible defaults, overriding specific fields."""
    defaults = {
        "filename": "IMG_001.jpg",
        "extension": "jpg",
        "media_type": "photo",
        "size_bytes": 1024,
        "size": "0.00 MB",
        "creation_date": "2024-01-01 12:00:00",
        "uuid": "abc-123",
        "icloud_status": "local",
    }
    defaults.update(overrides)
    return PhotoRecord(**defaults)


class TestBuildArgParser:
    def test_defaults(self):
        parser = build_arg_parser()
        args = parser.parse_args([])

        assert args.min_size_mb == 0.0
        assert args.output == DEFAULT_OUTPUT_FILE
        assert args.format == "csv"

    def test_min_size_mb(self):
        parser = build_arg_parser()
        args = parser.parse_args(["--min-size-mb", "100"])

        assert args.min_size_mb == 100.0

    def test_output_short_flag(self):
        parser = build_arg_parser()
        args = parser.parse_args(["-o", "/tmp/out.csv"])

        assert args.output == "/tmp/out.csv"

    def test_format_csv(self):
        parser = build_arg_parser()
        args = parser.parse_args(["-f", "csv"])

        assert args.format == "csv"

    def test_format_json(self):
        parser = build_arg_parser()
        args = parser.parse_args(["-f", "json"])

        assert args.format == "json"

    def test_invalid_format_rejected(self):
        parser = build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["-f", "xml"])

    def test_supported_formats_match_choices(self):
        parser = build_arg_parser()
        format_action = None
        for action in parser._actions:
            if "--format" in getattr(action, "option_strings", []):
                format_action = action
                break
        assert format_action is not None
        assert set(format_action.choices) == set(SUPPORTED_FORMATS)


class TestValidateOutputPath:
    def test_creates_parent_directories(self, tmp_path: Path):
        output = tmp_path / "a" / "b" / "report.csv"
        result = validate_output_path(str(output))

        assert result == output
        assert output.parent.exists()

    def test_warns_on_overwrite(self, tmp_path: Path, capsys):
        output = tmp_path / "existing.csv"
        output.write_text("old data")

        validate_output_path(str(output))

        stderr = capsys.readouterr().err
        assert "overwriting" in stderr

    def test_no_overwrite_warning_for_new_file(self, tmp_path: Path, capsys):
        output = tmp_path / "new.csv"

        validate_output_path(str(output))

        stderr = capsys.readouterr().err
        assert "overwriting" not in stderr

    def test_returns_path_object(self, tmp_path: Path):
        output = tmp_path / "report.csv"
        result = validate_output_path(str(output))

        assert isinstance(result, Path)
        assert result == output

    def test_exits_when_mkdir_fails(self, tmp_path: Path):
        # Use a path under /dev/null which can't have children
        with patch("iphoto_sizer.cli.Path.mkdir", side_effect=OSError("permission denied")):
            with pytest.raises(SystemExit) as exc_info:
                validate_output_path(str(tmp_path / "sub" / "report.csv"))
            assert exc_info.value.code == 1

    def test_exits_on_insufficient_disk_space(self, tmp_path: Path):
        output = tmp_path / "report.csv"
        fake_usage = SimpleNamespace(free=1024)  # 1 KB — way below 50 MB minimum
        with patch("iphoto_sizer.cli.shutil.disk_usage", return_value=fake_usage):
            with pytest.raises(SystemExit) as exc_info:
                validate_output_path(str(output))
            assert exc_info.value.code == 1

    def test_insufficient_disk_space_message(self, tmp_path: Path, capsys):
        output = tmp_path / "report.csv"
        fake_usage = SimpleNamespace(free=1024)
        with patch("iphoto_sizer.cli.shutil.disk_usage", return_value=fake_usage):
            with pytest.raises(SystemExit):
                validate_output_path(str(output))
        stderr = capsys.readouterr().err
        assert "Insufficient disk space" in stderr

    def test_disk_usage_oserror_proceeds_with_warning(self, tmp_path: Path, capsys):
        output = tmp_path / "report.csv"
        with patch("iphoto_sizer.cli.shutil.disk_usage", side_effect=OSError("network mount")):
            result = validate_output_path(str(output))
        assert result == output
        stderr = capsys.readouterr().err
        assert "could not check disk space" in stderr


class TestPrintSummary:
    def test_empty_records(self, capsys):
        print_summary([])

        stderr = capsys.readouterr().err
        assert "No items found" in stderr

    def test_displays_total_count(self, capsys):
        records = [_make_record(size_bytes=i * 100) for i in range(5)]
        print_summary(records)

        stderr = capsys.readouterr().err
        assert "Total items: 5" in stderr

    def test_displays_total_size(self, capsys):
        records = [_make_record(size_bytes=1024**2)]
        print_summary(records)

        stderr = capsys.readouterr().err
        assert "1.00 MB" in stderr

    def test_respects_top_n(self, capsys):
        records = [_make_record(filename=f"file_{i}.jpg", size_bytes=i * 100) for i in range(20)]
        print_summary(records, top_n=3)

        stderr = capsys.readouterr().err
        assert "Top 3" in stderr

    def test_top_n_capped_to_record_count(self, capsys):
        records = [_make_record(size_bytes=100)]
        print_summary(records, top_n=10)

        stderr = capsys.readouterr().err
        assert "Top 1" in stderr

    def test_output_goes_to_stderr(self, capsys):
        records = [_make_record()]
        print_summary(records)

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err != ""


def _fake_photo(**overrides: object) -> SimpleNamespace:
    """Create a fake PhotoInfo-like object for pipeline tests."""
    from datetime import datetime

    defaults = {
        "original_filename": "IMG_001.jpg",
        "original_filesize": 5_000_000,
        "ismovie": False,
        "date": datetime(2024, 6, 15, 14, 30, 0),
        "uuid": "ABC-123",
        "ismissing": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestRun:
    """Tests for the full _run pipeline."""

    def _run_with_args(self, args: list[str], photos: list[SimpleNamespace]) -> None:
        """Run the pipeline with the given CLI args and fake photos."""
        mock_db = MagicMock()
        mock_db.photos.return_value = photos

        with (
            patch("iphoto_sizer.cli.build_arg_parser") as mock_parser,
            patch("iphoto_sizer.cli.load_photos_db", return_value=mock_db),
        ):
            mock_parser.return_value.parse_args.return_value = (
                build_arg_parser().parse_args(args)
            )
            _run()

    def test_produces_csv_output(self, tmp_path: Path):
        output = tmp_path / "report.csv"
        photos = [_fake_photo(), _fake_photo(original_filename="b.mov", ismovie=True)]

        self._run_with_args(["-o", str(output)], photos)

        assert output.exists()
        with output.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    def test_produces_json_output(self, tmp_path: Path):
        output = tmp_path / "report.json"
        photos = [_fake_photo()]

        self._run_with_args(["-o", str(output), "-f", "json"], photos)

        data = json.loads(output.read_text())
        assert len(data) == 1

    def test_min_size_filters(self, tmp_path: Path):
        output = tmp_path / "report.csv"
        photos = [
            _fake_photo(original_filesize=100),
            _fake_photo(original_filename="big.mov", original_filesize=500_000_000),
        ]

        self._run_with_args(["-o", str(output), "--min-size-mb", "100"], photos)

        with output.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["filename"] == "big.mov"

    def test_sorts_by_size_descending(self, tmp_path: Path):
        output = tmp_path / "report.csv"
        photos = [
            _fake_photo(original_filename="small.jpg", original_filesize=100),
            _fake_photo(original_filename="big.jpg", original_filesize=999_999),
            _fake_photo(original_filename="mid.jpg", original_filesize=5000),
        ]

        self._run_with_args(["-o", str(output)], photos)

        with output.open() as f:
            rows = list(csv.DictReader(f))
        filenames = [r["filename"] for r in rows]
        assert filenames == ["big.jpg", "mid.jpg", "small.jpg"]

    def test_negative_min_size_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            self._run_with_args(["--min-size-mb", "-5"], [])
        assert exc_info.value.code == 1

    def test_skips_bad_photos_and_continues(self, tmp_path: Path, capsys):
        output = tmp_path / "report.csv"
        good_photo = _fake_photo()
        # A photo that will raise during conversion
        bad_photo = SimpleNamespace(
            original_filename=None,
            original_filesize="not_a_number",
            ismovie=False,
            date=None,
            uuid="BAD-UUID",
            ismissing=False,
        )

        self._run_with_args(["-o", str(output)], [bad_photo, good_photo])

        stderr = capsys.readouterr().err
        assert "Skipped 1 item(s)" in stderr
        with output.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1

    def test_reports_format_in_output_message(self, tmp_path: Path, capsys):
        output = tmp_path / "report.json"
        self._run_with_args(["-o", str(output), "-f", "json"], [_fake_photo()])

        stderr = capsys.readouterr().err
        assert "JSON written to" in stderr


class TestMain:
    def test_keyboard_interrupt_exits_130(self, capsys):
        with patch("iphoto_sizer.cli._run", side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 130
        stderr = capsys.readouterr().err
        assert "Interrupted" in stderr
