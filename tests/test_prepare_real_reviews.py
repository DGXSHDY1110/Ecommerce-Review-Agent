"""Tests for scripts/prepare_real_reviews.py — CSV cleaning and field mapping.

Verifies field alias mapping, filtering of invalid rows, and output correctness.
"""

import csv
import os
import sys
from pathlib import Path

import pytest

# Ensure the scripts directory is importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from prepare_real_reviews import (
    CANONICAL_FIELDS,
    DEFAULT_VALUES,
    FIELD_ALIASES,
    build_field_map,
    clean_review_text,
    parse_rating,
    prepare,
)


# ── Unit tests: parse_rating ───────────────────────────────────────────────────

class TestParseRating:
    def test_valid_ratings(self):
        """Valid 1-5 ratings should parse correctly."""
        for val, expected in [("1", 1), ("3", 3), ("5", 5), ("  4  ", 4)]:
            assert parse_rating(val, 0) == expected

    def test_string_float_rating(self):
        """'4.0' should parse as 4."""
        assert parse_rating("4.0", 0) == 4
        assert parse_rating("3.7", 0) == 3  # truncation

    def test_invalid_ratings_return_none(self):
        """Out-of-range or non-numeric ratings should return None."""
        for val in ["0", "6", "10", "abc", "", None, "-1"]:
            assert parse_rating(str(val) if val is not None else "", 0) is None


# ── Unit tests: clean_review_text ──────────────────────────────────────────────

class TestCleanReviewText:
    def test_normal_text(self):
        """Normal text returns stripped."""
        assert clean_review_text("  hello world  ") == "hello world"

    def test_empty_returns_none(self):
        """Empty or whitespace-only returns None."""
        assert clean_review_text("") is None
        assert clean_review_text("   ") is None
        assert clean_review_text("\t\n") is None

    def test_none_returns_none(self):
        """None input returns None."""
        assert clean_review_text(None) is None  # type: ignore[arg-type]


# ── Unit tests: build_field_map ────────────────────────────────────────────────

class TestBuildFieldMap:
    def test_standard_fields(self):
        """Standard column names map directly."""
        header = ["review_id", "platform", "rating", "review_text"]
        mapping = build_field_map(header)
        assert mapping["review_id"] == "review_id"
        assert mapping["platform"] == "platform"

    def test_alias_fields(self):
        """Alias names map to canonical names."""
        header = ["id", "source", "stars", "text"]
        mapping = build_field_map(header)
        assert mapping["id"] == "review_id"
        assert mapping["source"] == "platform"
        assert mapping["stars"] == "rating"
        assert mapping["text"] == "review_text"

    def test_mixed_fields(self):
        """Mix of standard and alias fields."""
        header = ["review_id", "title", "score", "body", "marketplace"]
        mapping = build_field_map(header)
        assert mapping["review_id"] == "review_id"
        assert mapping["title"] == "product_name"
        assert mapping["score"] == "rating"
        assert mapping["body"] == "review_text"
        assert mapping["marketplace"] == "platform"

    def test_unmapped_columns_ignored(self):
        """Unknown columns should just be ignored (with warning)."""
        header = ["review_id", "rating", "review_text", "some_random_column"]
        mapping = build_field_map(header)
        assert "some_random_column" not in mapping


# ── Integration tests: prepare() with temp files ───────────────────────────────

class TestPrepare:
    """End-to-end tests for the prepare() function using temp CSV files."""

    @staticmethod
    def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for row in rows:
                writer.writerow(row)

    @staticmethod
    def _read_csv(path: Path) -> list[dict]:
        with open(path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_basic_prepare(self, tmp_path: Path):
        """Standard fields pass through unchanged."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        self._write_csv(
            input_csv,
            ["review_id", "platform", "product_name", "rating", "review_text", "country", "created_at"],
            [
                ["r001", "Amazon", "Camera A", "2", "Battery issue.", "US", "2026-06-01"],
                ["r002", "Shopify", "Camera B", "4", "Great quality.", "DE", "2026-06-02"],
            ],
        )

        written, skipped = prepare(str(input_csv), str(output_csv), force_overwrite=True)
        assert written == 2
        assert skipped == 0

        result = self._read_csv(output_csv)
        assert len(result) == 2
        assert result[0]["review_id"] == "r001"
        assert result[0]["rating"] == "2"
        assert result[0]["review_text"] == "Battery issue."

    def test_alias_fields_mapped(self, tmp_path: Path):
        """Alias columns should be mapped to canonical names."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        self._write_csv(
            input_csv,
            ["id", "source", "title", "score", "text", "region", "date"],
            [
                ["r001", "Amazon", "Camera", "3", "It works.", "US", "2026-06-01"],
            ],
        )

        written, skipped = prepare(str(input_csv), str(output_csv), force_overwrite=True)
        assert written == 1
        assert skipped == 0

        result = self._read_csv(output_csv)
        assert result[0]["review_id"] == "r001"
        assert result[0]["platform"] == "Amazon"
        assert result[0]["product_name"] == "Camera"
        assert result[0]["rating"] == "3"
        assert result[0]["review_text"] == "It works."
        assert result[0]["country"] == "US"

    def test_empty_review_text_filtered(self, tmp_path: Path):
        """Rows with empty review_text should be skipped."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        self._write_csv(
            input_csv,
            ["review_id", "platform", "rating", "review_text", "country", "created_at"],
            [
                ["r001", "Amazon", "3", "", "US", "2026-06-01"],        # empty text
                ["r002", "Shopify", "4", "   ", "DE", "2026-06-02"],    # whitespace only
                ["r003", "Amazon", "5", "Valid review.", "US", "2026-06-03"],
            ],
        )

        written, skipped = prepare(str(input_csv), str(output_csv), force_overwrite=True)
        assert written == 1
        assert skipped == 2
        result = self._read_csv(output_csv)
        assert result[0]["review_id"] == "r003"

    def test_invalid_rating_filtered(self, tmp_path: Path):
        """Rows with invalid rating should be skipped."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        self._write_csv(
            input_csv,
            ["review_id", "platform", "rating", "review_text", "country", "created_at"],
            [
                ["r001", "Amazon", "0", "Bad.", "US", "2026-06-01"],       # rating too low
                ["r002", "Shopify", "6", "Great!", "DE", "2026-06-02"],    # rating too high
                ["r003", "Amazon", "abc", "Okay.", "US", "2026-06-03"],    # non-numeric
                ["r004", "Amazon", "4", "Valid.", "US", "2026-06-04"],
            ],
        )

        written, skipped = prepare(str(input_csv), str(output_csv), force_overwrite=True)
        assert written == 1
        assert skipped == 3
        result = self._read_csv(output_csv)
        assert result[0]["review_id"] == "r004"

    def test_missing_optional_fields_get_defaults(self, tmp_path: Path):
        """Missing optional fields should get default values."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        # Only review_id, rating, review_text are truly required
        self._write_csv(
            input_csv,
            ["review_id", "rating", "review_text"],
            [
                ["r001", "3", "A review with minimal fields."],
            ],
        )

        written, skipped = prepare(str(input_csv), str(output_csv), force_overwrite=True)
        assert written == 1
        result = self._read_csv(output_csv)
        assert result[0]["platform"] == DEFAULT_VALUES["platform"]
        assert result[0]["product_name"] == DEFAULT_VALUES["product_name"]
        assert result[0]["country"] == DEFAULT_VALUES["country"]
        assert result[0]["created_at"] == DEFAULT_VALUES["created_at"]

    def test_auto_generated_review_id(self, tmp_path: Path):
        """Missing review_id should be auto-generated."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        self._write_csv(
            input_csv,
            ["review_text", "rating"],
            [
                ["First review.", "3"],
                ["Second review.", "4"],
            ],
        )

        written, skipped = prepare(str(input_csv), str(output_csv), force_overwrite=True)
        assert written == 2
        result = self._read_csv(output_csv)
        assert result[0]["review_id"] == "r0001"
        assert result[1]["review_id"] == "r0002"

    def test_output_csv_has_exact_canonical_fields(self, tmp_path: Path):
        """Output CSV must have exactly the CANONICAL_FIELDS as header."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        self._write_csv(
            input_csv,
            ["review_id", "rating", "review_text"],
            [["r001", "3", "Test."]],
        )

        prepare(str(input_csv), str(output_csv), force_overwrite=True)

        with open(output_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == CANONICAL_FIELDS

    def test_no_overwrite_without_force(self, tmp_path: Path):
        """Should refuse to overwrite existing output without --force."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        # Pre-create output file
        output_csv.write_text("existing")

        self._write_csv(
            input_csv,
            ["review_id", "rating", "review_text"],
            [["r001", "3", "Test."]],
        )

        with pytest.raises(SystemExit):
            prepare(str(input_csv), str(output_csv), force_overwrite=False)

    def test_force_overwrite(self, tmp_path: Path):
        """force_overwrite=True should allow overwriting."""
        input_csv = tmp_path / "input.csv"
        output_csv = tmp_path / "output.csv"

        output_csv.write_text("old data")

        self._write_csv(
            input_csv,
            ["review_id", "rating", "review_text"],
            [["r001", "3", "New data."]],
        )

        written, skipped = prepare(str(input_csv), str(output_csv), force_overwrite=True)
        assert written == 1
        result = self._read_csv(output_csv)
        assert result[0]["review_text"] == "New data."


# ── Test: real_reviews_sample.csv is readable ──────────────────────────────────

class TestRealReviewsSample:
    """Verify that the real_reviews_sample.csv is valid and readable."""

    def test_file_exists(self):
        """The real_reviews_sample.csv file should exist."""
        path = Path(__file__).resolve().parent.parent / "data" / "real_reviews_sample.csv"
        assert path.exists(), f"File not found: {path}"

    def test_file_is_valid_csv(self):
        """The file should be parseable as CSV."""
        path = Path(__file__).resolve().parent.parent / "data" / "real_reviews_sample.csv"
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) >= 40, f"Expected at least 40 reviews, got {len(rows)}"

    def test_all_rows_have_required_fields(self):
        """Every row should have all 7 required fields."""
        path = Path(__file__).resolve().parent.parent / "data" / "real_reviews_sample.csv"
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames is not None
            actual_fields = list(reader.fieldnames)
            for field in CANONICAL_FIELDS:
                assert field in actual_fields, f"Missing canonical field: {field}"

            for row in reader:
                for field in CANONICAL_FIELDS:
                    assert field in row, f"Missing field '{field}' in row {row.get('review_id', '?')}"

    def test_all_ratings_in_range(self):
        """All ratings should be between 1 and 5."""
        path = Path(__file__).resolve().parent.parent / "data" / "real_reviews_sample.csv"
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rating = int(row["rating"])
                assert 1 <= rating <= 5, f"Row {row['review_id']}: rating={rating}"

    def test_no_empty_review_text(self):
        """No row should have empty review_text."""
        path = Path(__file__).resolve().parent.parent / "data" / "real_reviews_sample.csv"
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                assert row["review_text"].strip(), f"Row {row['review_id']}: empty review_text"

    def test_readable_by_run_batch(self):
        """The CSV should be directly readable by run_batch's read_reviews_csv."""
        scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        from run_batch import read_reviews_csv

        path = str(Path(__file__).resolve().parent.parent / "data" / "real_reviews_sample.csv")
        reviews = read_reviews_csv(path)
        assert len(reviews) >= 40

    def test_limit_flag_respected(self):
        """--limit should limit the number of reviews read."""
        scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        from run_batch import read_reviews_csv

        path = str(Path(__file__).resolve().parent.parent / "data" / "real_reviews_sample.csv")
        reviews = read_reviews_csv(path, limit=5)
        assert len(reviews) == 5
        assert reviews[0].review_id == "r001"
        assert reviews[-1].review_id == "r005"
