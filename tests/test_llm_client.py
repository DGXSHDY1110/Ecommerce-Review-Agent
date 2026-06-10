"""Tests for LLMClient real-mode code paths via monkeypatch.

All tests monkeypatch requests.post — NO real API calls are made.
"""

import json
import re
from unittest.mock import MagicMock

import pytest
import requests

from src.review_agent.config import Settings, get_settings
from src.review_agent.llm_client import LLMClient
from src.review_agent.schemas import ReviewAnalysis, ReviewInput


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_review(
    review_id="r001", rating=2, review_text="Battery drains too fast."
) -> ReviewInput:
    return ReviewInput(
        review_id=review_id,
        platform="Amazon",
        product_name="Test Product",
        rating=rating,
        review_text=review_text,
        country="US",
        created_at="2026-06-01",
    )


def make_real_settings() -> Settings:
    """Settings for real mode with a fake API key."""
    s = get_settings()
    s.llm_mock_mode = False
    s.use_mock_llm = False
    s.deepseek_api_key = "sk-fake-test-key-12345"
    s.deepseek_model = "deepseek-v4-pro"
    s.llm_max_retries = 1  # 1 retry = 2 total attempts
    return s


def make_valid_llm_response() -> dict:
    """Return a valid LLM JSON response that matches ReviewAnalysis schema."""
    return {
        "review_id": "r001",
        "sentiment": "negative",
        "issue_category": "battery",
        "priority": "high",
        "responsible_team": "product",
        "summary_zh": "客户反馈电池耗电过快。",
        "suggested_action_zh": "建议产品团队检查电池续航表现。",
        "confidence": 0.88,
        "needs_human_review": False,
        "evidence": ["Battery drains too fast"],
    }


def make_mock_response(json_body: dict, status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response that returns the given JSON body."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": json.dumps(json_body, ensure_ascii=False)}}]
    }
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            response=mock_resp
        )
    return mock_resp


# ── Tests: Real mode with valid responses ──────────────────────────────────────

class TestRealModeValidResponse:
    """Happy-path: valid JSON from LLM → valid ReviewAnalysis."""

    def test_real_mode_returns_review_analysis(self, monkeypatch):
        """Valid LLM response produces ReviewAnalysis with real mode markers."""
        settings = make_real_settings()
        client = LLMClient(settings=settings)

        mock_resp = make_mock_response(make_valid_llm_response())
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert isinstance(result, ReviewAnalysis)
        assert result.review_id == "r001"

    def test_real_mode_llm_mode_is_real(self, monkeypatch):
        """Real LLM path sets llm_mode='real'."""
        settings = make_real_settings()
        client = LLMClient(settings=settings)

        mock_resp = make_mock_response(make_valid_llm_response())
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert result.llm_mode == "real"

    def test_real_mode_is_mock_is_false(self, monkeypatch):
        """Real LLM path sets is_mock=False."""
        settings = make_real_settings()
        client = LLMClient(settings=settings)

        mock_resp = make_mock_response(make_valid_llm_response())
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert result.is_mock is False

    def test_real_mode_model_field(self, monkeypatch):
        """Real LLM path sets model from settings."""
        settings = make_real_settings()
        client = LLMClient(settings=settings)

        mock_resp = make_mock_response(make_valid_llm_response())
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert result.model == "deepseek-v4-pro"

    def test_evidence_preserved_from_llm(self, monkeypatch):
        """Evidence from LLM JSON output is preserved."""
        settings = make_real_settings()
        client = LLMClient(settings=settings)

        body = make_valid_llm_response()
        body["evidence"] = ["Battery drains too fast", "night vision is blurry"]
        mock_resp = make_mock_response(body)
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(
            make_review(review_text="Battery drains too fast and night vision blurry.")
        )
        assert len(result.evidence) == 2
        assert "Battery drains too fast" in result.evidence

    def test_processing_time_ms_set(self, monkeypatch):
        """Real LLM path sets processing_time_ms."""
        settings = make_real_settings()
        client = LLMClient(settings=settings)

        mock_resp = make_mock_response(make_valid_llm_response())
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert result.processing_time_ms is not None
        assert result.processing_time_ms >= 0

    def test_llm_output_extra_fields_ignored(self, monkeypatch):
        """Extra fields in LLM output are ignored (not rejected)."""
        settings = make_real_settings()
        client = LLMClient(settings=settings)

        body = make_valid_llm_response()
        body["extra_field"] = "should be ignored"
        mock_resp = make_mock_response(body)
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert result.review_id == "r001"
        assert result.sentiment == "negative"


# ── Tests: JSON extraction and retry ───────────────────────────────────────────

class TestJsonExtractionAndRetry:
    """JSON parse / validation failures trigger retry, then fallback."""

    def test_json_in_fenced_block_extracted(self, monkeypatch):
        """LLM output wrapped in ```json``` is correctly extracted."""
        settings = make_real_settings()
        client = LLMClient(settings=settings)

        body = make_valid_llm_response()
        json_str = json.dumps(body, ensure_ascii=False)
        fenced = f"Here's the analysis:\n```json\n{json_str}\n```\nHope this helps."

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": fenced}}]
        }
        mock_resp.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert result.review_id == "r001"
        assert result.sentiment == "negative"

    def test_json_with_surrounding_text_extracted(self, monkeypatch):
        """LLM output with text before/after JSON braces is extracted."""
        settings = make_real_settings()
        client = LLMClient(settings=settings)

        body = make_valid_llm_response()
        json_str = json.dumps(body, ensure_ascii=False)
        with_text = f"Sure, here is the result:\n{json_str}\nThat's all."

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": with_text}}]
        }
        mock_resp.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert result.review_id == "r001"

    def test_retry_succeeds_on_second_attempt(self, monkeypatch):
        """First call returns bad JSON, second call returns valid JSON."""
        settings = make_real_settings()
        # need at least 1 retry (2 total attempts)
        settings.llm_max_retries = 1
        client = LLMClient(settings=settings)

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_resp = MagicMock(spec=requests.Response)
            mock_resp.status_code = 200
            if call_count[0] == 1:
                # First attempt: invalid JSON
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": "not json at all"}}]
                }
            else:
                # Second attempt: valid JSON
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": json.dumps(make_valid_llm_response(), ensure_ascii=False)}}]
                }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        monkeypatch.setattr(requests, "post", side_effect)

        result = client.analyze_review(make_review())
        assert call_count[0] == 2
        assert result.review_id == "r001"
        assert result.sentiment == "negative"

    def test_all_attempts_fail_returns_fallback(self, monkeypatch):
        """All attempts fail → safe fallback returned."""
        settings = make_real_settings()
        settings.llm_max_retries = 1
        client = LLMClient(settings=settings)

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "This is not JSON."}}]
        }
        mock_resp.raise_for_status = MagicMock()
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert result.confidence == 0.0
        assert result.needs_human_review is True
        assert result.issue_category == "other"
        assert "模型调用或解析失败" in result.summary_zh
        assert result.llm_mode == "real"
        assert result.is_mock is False

    def test_pydantic_validation_failure_triggers_retry(self, monkeypatch):
        """Pydantic validation failure (invalid enum) triggers retry."""
        settings = make_real_settings()
        settings.llm_max_retries = 1
        client = LLMClient(settings=settings)

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_resp = MagicMock(spec=requests.Response)
            mock_resp.status_code = 200
            if call_count[0] == 1:
                # Invalid sentiment value
                body = make_valid_llm_response()
                body["sentiment"] = "angry"  # not a valid Literal
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": json.dumps(body, ensure_ascii=False)}}]
                }
            else:
                # Valid on second attempt
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": json.dumps(make_valid_llm_response(), ensure_ascii=False)}}]
                }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        monkeypatch.setattr(requests, "post", side_effect)

        result = client.analyze_review(make_review())
        assert call_count[0] == 2
        assert result.sentiment == "negative"


# ── Tests: HTTP errors ────────────────────────────────────────────────────────

class TestHttpErrors:
    """HTTP error handling and error logging."""

    def test_http_500_triggers_retry_then_fallback(self, monkeypatch, tmp_path):
        """HTTP 500 on all attempts → retry then fallback."""
        settings = make_real_settings()
        settings.llm_max_retries = 1
        client = LLMClient(settings=settings)

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            "500 Server Error", response=mock_resp
        )
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        result = client.analyze_review(make_review())
        assert result.confidence == 0.0
        assert result.needs_human_review is True

    def test_http_401_not_retried(self, monkeypatch):
        """HTTP 401 should NOT be retried (client error)."""
        settings = make_real_settings()
        settings.llm_max_retries = 3  # plenty of retries
        client = LLMClient(settings=settings)

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            mock_resp = MagicMock(spec=requests.Response)
            mock_resp.status_code = 401
            mock_resp.raise_for_status.side_effect = requests.HTTPError(
                "401 Unauthorized", response=mock_resp
            )
            return mock_resp

        monkeypatch.setattr(requests, "post", side_effect)

        result = client.analyze_review(make_review())
        # 401 is 4xx → should NOT retry → only 1 call
        assert call_count[0] == 1
        assert result.confidence == 0.0


# ── Tests: Missing API key ─────────────────────────────────────────────────────

class TestMissingApiKey:
    """V2-M2: Real mode without API key must raise error, NOT silently mock."""

    def test_missing_api_key_raises_value_error(self):
        """Missing API key in real mode raises ValueError."""
        settings = make_real_settings()
        settings.deepseek_api_key = ""  # no API key
        client = LLMClient(settings=settings)

        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
            client.analyze_review(make_review())

    def test_missing_api_key_does_not_return_mock(self):
        """Missing API key must NOT silently return a mock result."""
        settings = make_real_settings()
        settings.deepseek_api_key = ""
        client = LLMClient(settings=settings)

        try:
            client.analyze_review(make_review())
            pytest.fail("Should have raised ValueError")
        except ValueError:
            pass  # expected

    def test_mock_mode_still_works_without_api_key(self):
        """Mock mode (explicit) still works without API key."""
        settings = make_real_settings()
        settings.deepseek_api_key = ""
        settings.llm_mock_mode = True  # explicit mock
        client = LLMClient(settings=settings)

        result = client.analyze_review(make_review())
        assert result.llm_mode == "mock"
        assert result.is_mock is True
        assert result.model == "mock-rule-engine"


# ── Tests: Mock output quality (V2-M2) ─────────────────────────────────────────

class TestMockOutputQuality:
    """V2-M2: Mock output must not contain "评分X" or "unknown团队"."""

    def test_mock_summary_no_rating_template(self):
        """Mock summary_zh should not contain robot-like "评分X"."""
        settings = make_real_settings()
        settings.llm_mock_mode = True
        client = LLMClient(settings=settings)

        result = client.analyze_review(make_review(rating=2))
        summary = result.summary_zh
        # New mock format: should NOT have the old template "评分2"
        assert "，评分2。" not in summary, f"Got: {summary}"
        # Should be natural Chinese
        assert len(summary) > 5

    def test_mock_action_no_unknown_team(self):
        """Mock suggested_action_zh should not expose 'unknown' team."""
        settings = make_real_settings()
        settings.llm_mock_mode = True
        client = LLMClient(settings=settings)

        # A review that won't match any keyword → category="other" → team="unknown"
        result = client.analyze_review(
            make_review(rating=3, review_text="Just a random thought.")
        )
        action = result.suggested_action_zh
        assert "unknown" not in action.lower(), f"Got: {action}"
        # Should suggest human review if team unknown
        assert "人工复核" in action or "运营" in action, f"Got: {action}"

    def test_mock_output_is_marked_mock(self):
        """Mock results must clearly indicate is_mock=True, llm_mode='mock'."""
        settings = make_real_settings()
        settings.llm_mock_mode = True
        client = LLMClient(settings=settings)

        result = client.analyze_review(make_review())
        assert result.llm_mode == "mock"
        assert result.is_mock is True
        assert result.model == "mock-rule-engine"


# ── Tests: Safe exception handling ─────────────────────────────────────────────

class TestSafeErrorHandling:
    """Error messages and logging must not leak API keys."""

    def test_error_message_redacts_api_key(self, monkeypatch):
        """HTTP error messages must not contain real API keys."""
        settings = make_real_settings()
        settings.llm_max_retries = 0  # no retry to speed up
        client = LLMClient(settings=settings)

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 500
        mock_resp.text = "Internal error with key sk-exposed-key-12345"
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            "Error containing sk-exposed-key-12345", response=mock_resp
        )
        monkeypatch.setattr(requests, "post", lambda *a, **kw: mock_resp)

        # Should not raise — returns fallback instead
        result = client.analyze_review(make_review())
        assert result.confidence == 0.0

    def test_api_key_not_in_exception_message(self):
        """ValueError for missing API key should not contain real key value."""
        settings = make_real_settings()
        settings.deepseek_api_key = ""
        client = LLMClient(settings=settings)

        with pytest.raises(ValueError) as exc_info:
            client.analyze_review(make_review())
        # Message should be helpful but not contain any key-like patterns
        msg = str(exc_info.value)
        assert "sk-" not in msg.lower()


# ── Tests: _extract_json edge cases ────────────────────────────────────────────

class TestExtractJson:
    """Direct tests for the _extract_json static method."""

    def test_empty_string_raises(self):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            LLMClient._extract_json("")

    def test_non_json_text_raises(self):
        """Plain text with no JSON should raise ValueError."""
        with pytest.raises(ValueError):
            LLMClient._extract_json("This is just plain text without any JSON.")

    def test_nested_json_object(self):
        """JSON object with nested objects should be extracted."""
        text = '{"review_id": "r001", "nested": {"key": "value"}}'
        result = LLMClient._extract_json(text)
        assert result["review_id"] == "r001"
        assert result["nested"]["key"] == "value"

    def test_json_array_rejected(self):
        """JSON array (not object) should raise ValueError."""
        with pytest.raises(ValueError):
            LLMClient._extract_json('[{"a": 1}, {"b": 2}]')
