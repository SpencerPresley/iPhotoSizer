"""Tests for iphoto_sizer.writers."""

import csv
import json
from pathlib import Path

from iphoto_sizer.models import CSV_COLUMNS
from iphoto_sizer.writers import write_csv, write_json
from tests.conftest import make_record


class TestWriteCSV:
    def test_writes_header_row(self, tmp_path: Path):
        output = tmp_path / "test.csv"
        write_csv([], output)

        with output.open() as f:
            reader = csv.reader(f)
            header = next(reader)
        assert tuple(header) == CSV_COLUMNS

    def test_writes_records(self, tmp_path: Path):
        records = [
            make_record(filename="a.jpg", size_bytes=200),
            make_record(filename="b.mov", size_bytes=100),
        ]
        output = tmp_path / "test.csv"
        write_csv(records, output)

        with output.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["filename"] == "a.jpg"
        assert rows[0]["size_bytes"] == "200"
        assert rows[1]["filename"] == "b.mov"

    def test_empty_records_writes_header_only(self, tmp_path: Path):
        output = tmp_path / "test.csv"
        write_csv([], output)

        text = output.read_text()
        lines = text.strip().split("\n")
        assert len(lines) == 1


class TestWriteJSON:
    def test_writes_valid_json(self, tmp_path: Path):
        records = [make_record(filename="a.jpg")]
        output = tmp_path / "test.json"
        write_json(records, output)

        data = json.loads(output.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["filename"] == "a.jpg"

    def test_empty_records_writes_empty_array(self, tmp_path: Path):
        output = tmp_path / "test.json"
        write_json([], output)

        data = json.loads(output.read_text())
        assert data == []

    def test_all_fields_present(self, tmp_path: Path):
        records = [make_record()]
        output = tmp_path / "test.json"
        write_json(records, output)

        data = json.loads(output.read_text())
        assert set(data[0].keys()) == set(CSV_COLUMNS)

    def test_json_is_indented(self, tmp_path: Path):
        records = [make_record()]
        output = tmp_path / "test.json"
        write_json(records, output)

        text = output.read_text()
        assert "\n" in text
        assert "    " in text
