"""Tests for error logging utility (src/review_agent/utils.py).

Verifies that error_cases.jsonl is created correctly, contains valid JSONL,
does not leak API keys, and handles write failures gracefully.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Use the real module but redirect the log path for tests
from src.review_agent import utils as error_utils
from src.review_agent.utils import log_error_case, _sanitise_output


class TestLogErrorCase:
    """Tests for the log_error_case function."""

    def test_creates_error_log_file(self, tmp_path: Path):
        """log_error_case should create error_cases.jsonl if it doesn't exist."""
        # Temporarily override the error log path
        original_path = error_utils.ERROR_LOG_PATH
        test_path = tmp_path / "error_cases.jsonl"
        error_utils.ERROR_LOG_PATH = test_path

        try:
            log_error_case(
                review_id="r001",
                error_type="JSON_PARSE_FAILED",
                error_message="Test error",
            )
            assert test_path.exists()
            assert test_path.stat().st_size > 0
        finally:
            error_utils.ERROR_LOG_PATH = original_path

    def test_writes_valid_jsonl(self, tmp_path: Path):
        """Each line should be a valid JSON object."""
        original_path = error_utils.ERROR_LOG_PATH
        test_path = tmp_path / "error_cases.jsonl"
        error_utils.ERROR_LOG_PATH = test_path

        try:
            log_error_case(
                review_id="r001",
                error_type="JSON_PARSE_FAILED",
                error_message="Test error",
            )
            log_error_case(
                review_id="r002",
                error_type="API_TIMEOUT",
                error_message="Timeout after 30s",
            )

            with open(test_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) == 2
            for line in lines:
                parsed = json.loads(line.strip())
                assert isinstance(parsed, dict)
        finally:
            error_utils.ERROR_LOG_PATH = original_path

    def test_entry_has_required_fields(self, tmp_path: Path):
        """Each error entry must have timestamp, review_id, error_type, etc."""
        original_path = error_utils.ERROR_LOG_PATH
        test_path = tmp_path / "error_cases.jsonl"
        error_utils.ERROR_LOG_PATH = test_path

        try:
            log_error_case(
                review_id="r001",
                error_type="TEST_ERROR",
                error_message="Test message",
            )

            with open(test_path, "r", encoding="utf-8") as f:
                entry = json.loads(f.readline().strip())

            assert "timestamp" in entry
            assert entry["review_id"] == "r001"
            assert entry["error_type"] == "TEST_ERROR"
            assert entry["error_message"] == "Test message"
            assert "fallback_used" in entry
            assert "needs_human_review" in entry
        finally:
            error_utils.ERROR_LOG_PATH = original_path

    def test_raw_output_truncated(self, tmp_path: Path):
        """Raw output longer than 1000 chars should be truncated."""
        original_path = error_utils.ERROR_LOG_PATH
        test_path = tmp_path / "error_cases.jsonl"
        error_utils.ERROR_LOG_PATH = test_path

        try:
            long_output = "x" * 2000
            log_error_case(
                review_id="r001",
                error_type="TEST",
                error_message="Test",
                raw_output=long_output,
            )

            with open(test_path, "r", encoding="utf-8") as f:
                entry = json.loads(f.readline().strip())

            assert "raw_output" in entry
            assert len(entry["raw_output"]) <= 1000
        finally:
            error_utils.ERROR_LOG_PATH = original_path

    def test_does_not_contain_api_key(self, tmp_path: Path):
        """Error log entries must not contain API key patterns."""
        original_path = error_utils.ERROR_LOG_PATH
        test_path = tmp_path / "error_cases.jsonl"
        error_utils.ERROR_LOG_PATH = test_path

        try:
            # Simulate an error message that might contain sensitive data
            log_error_case(
                review_id="r001",
                error_type="API_ERROR",
                error_message="Request failed",
                raw_output='{"Authorization": "Bearer sk-abc123def456"}',
            )

            with open(test_path, "r", encoding="utf-8") as f:
                content = f.read()

            # The raw content should not contain the API key pattern
            assert "sk-abc123def456" not in content.lower()
        finally:
            error_utils.ERROR_LOG_PATH = original_path

    def test_write_failure_does_not_raise(self, tmp_path: Path):
        """If writing fails (e.g., permission error), no exception should propagate."""
        original_path = error_utils.ERROR_LOG_PATH

        # Point to a path where writing would fail (directory is a file)
        bad_path = tmp_path / "not_a_dir" / "error_cases.jsonl"
        # Create "not_a_dir" as a regular file so that mkdir fails
        bad_path.parent.write_text("blocked")

        error_utils.ERROR_LOG_PATH = bad_path

        try:
            # This should NOT raise
            log_error_case(
                review_id="r001",
                error_type="TEST",
                error_message="Should not crash",
            )
        finally:
            error_utils.ERROR_LOG_PATH = original_path


class TestSanitiseOutput:
    """Tests for the _sanitise_output helper."""

    def test_redacts_bearer_token(self):
        """Should redact Authorization: Bearer patterns."""
        text = '{"Authorization": "Bearer sk-very-secret-key-12345"}'
        result = _sanitise_output(text)
        assert "sk-very-secret-key-12345" not in result
        assert "***REDACTED***" in result

    def test_redacts_api_key_field(self):
        """Should redact fields named api_key."""
        text = '{"api_key": "my-secret-key"}'
        result = _sanitise_output(text)
        assert "my-secret-key" not in result
        assert "***REDACTED***" in result

    def test_preserves_harmless_fields(self):
        """Non-sensitive fields should be unchanged."""
        text = '{"review_id": "r001", "confidence": 0.5}'
        result = _sanitise_output(text)
        assert "r001" in result
        assert "0.5" in result

    def test_handles_empty_string(self):
        """Empty input should not crash."""
        result = _sanitise_output("")
        assert result == ""

    def test_handles_non_json_text(self):
        """Non-JSON text should pass through mostly unchanged."""
        result = _sanitise_output("Just a plain error message")
        assert "Just a plain error message" in result
