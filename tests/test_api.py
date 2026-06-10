"""Tests for the FastAPI service endpoints.

All tests use mock mode — no real DeepSeek API calls are made.
"""

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def enable_mock_mode(monkeypatch):
    """Ensure every test runs in mock mode (V2-M1: set both canonical and legacy env vars)."""
    monkeypatch.setenv("USE_MOCK_LLM", "true")
    monkeypatch.setenv("LLM_MOCK_MODE", "true")


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    from src.review_agent.api import app
    return TestClient(app)


# ── Helper ─────────────────────────────────────────────────────────────────────

def make_review_payload(
    review_id="r001",
    platform="Amazon",
    product_name="Test Camera",
    rating=2,
    review_text="Battery drains too fast and the night vision is blurry.",
    country="US",
    created_at="2026-06-01",
) -> dict:
    """Build a minimal valid review payload for POST /api/v1/analyze."""
    return {
        "review_id": review_id,
        "platform": platform,
        "product_name": product_name,
        "rating": rating,
        "review_text": review_text,
        "country": country,
        "created_at": created_at,
    }


# ── Health endpoint ────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    def test_health_returns_200(self, client):
        """GET /api/v1/health returns HTTP 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_returns_correct_status(self, client):
        """GET /api/v1/health returns status=ok."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_returns_service_name(self, client):
        """GET /api/v1/health returns service=ecommerce-review-agent."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["service"] == "ecommerce-review-agent"

    def test_health_response_schema(self, client):
        """GET /api/v1/health response has exactly status and service keys."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert set(data.keys()) == {"status", "service"}


# ── Single analyze endpoint ────────────────────────────────────────────────────

class TestAnalyzeEndpoint:
    """Tests for POST /api/v1/analyze."""

    def test_analyze_returns_200(self, client):
        """POST /api/v1/analyze should return HTTP 200 with valid input."""
        response = client.post("/api/v1/analyze", json=make_review_payload())
        assert response.status_code == 200

    def test_analyze_returns_review_id(self, client):
        """Response must contain the review_id from the request."""
        response = client.post("/api/v1/analyze", json=make_review_payload(review_id="r999"))
        data = response.json()
        assert data["review_id"] == "r999"

    def test_analyze_returns_required_fields(self, client):
        """Response must contain all expected classification fields."""
        response = client.post("/api/v1/analyze", json=make_review_payload())
        data = response.json()
        required_fields = [
            "review_id",
            "sentiment",
            "issue_category",
            "priority",
            "responsible_team",
            "summary_zh",
            "suggested_action_zh",
            "confidence",
            "needs_human_review",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_analyze_confidence_in_range(self, client):
        """Confidence must be between 0.0 and 1.0."""
        response = client.post("/api/v1/analyze", json=make_review_payload())
        data = response.json()
        assert 0.0 <= data["confidence"] <= 1.0

    def test_analyze_needs_human_review_is_bool(self, client):
        """needs_human_review must be a boolean."""
        response = client.post("/api/v1/analyze", json=make_review_payload())
        data = response.json()
        assert isinstance(data["needs_human_review"], bool)

    def test_analyze_low_rating_negative_sentiment(self, client):
        """Rating <= 2 review should be classified as negative in mock mode."""
        response = client.post(
            "/api/v1/analyze",
            json=make_review_payload(rating=1, review_text="Terrible product."),
        )
        data = response.json()
        assert data["sentiment"] == "negative"

    def test_analyze_high_rating_positive_sentiment(self, client):
        """Rating >= 4 review should be classified as positive in mock mode."""
        response = client.post(
            "/api/v1/analyze",
            json=make_review_payload(rating=5, review_text="Excellent product!"),
        )
        data = response.json()
        assert data["sentiment"] == "positive"

    def test_analyze_empty_review_text_returns_422(self, client):
        """Empty review_text should return HTTP 422 (Pydantic validation)."""
        response = client.post(
            "/api/v1/analyze",
            json=make_review_payload(review_text=""),
        )
        assert response.status_code == 422

    def test_analyze_whitespace_review_text_returns_422(self, client):
        """Whitespace-only review_text should return HTTP 422."""
        response = client.post(
            "/api/v1/analyze",
            json=make_review_payload(review_text="   "),
        )
        assert response.status_code == 422

    def test_analyze_rating_below_1_returns_422(self, client):
        """Rating < 1 should return HTTP 422."""
        response = client.post(
            "/api/v1/analyze",
            json=make_review_payload(rating=0),
        )
        assert response.status_code == 422

    def test_analyze_rating_above_5_returns_422(self, client):
        """Rating > 5 should return HTTP 422."""
        response = client.post(
            "/api/v1/analyze",
            json=make_review_payload(rating=6),
        )
        assert response.status_code == 422

    def test_analyze_missing_field_returns_422(self, client):
        """Missing required field should return HTTP 422."""
        payload = make_review_payload()
        del payload["review_text"]
        response = client.post("/api/v1/analyze", json=payload)
        assert response.status_code == 422

    # ── V2-M1: New fields in analyze response ─────────────────────────────

    def test_analyze_returns_evidence_field(self, client):
        """Response must include evidence field (list)."""
        response = client.post("/api/v1/analyze", json=make_review_payload())
        data = response.json()
        assert "evidence" in data, "Missing evidence field"
        assert isinstance(data["evidence"], list)

    def test_analyze_returns_llm_mode_field(self, client):
        """Response must include llm_mode field."""
        response = client.post("/api/v1/analyze", json=make_review_payload())
        data = response.json()
        assert "llm_mode" in data, "Missing llm_mode field"
        assert data["llm_mode"] in ("real", "mock")

    def test_analyze_returns_is_mock_field(self, client):
        """Response must include is_mock boolean field."""
        response = client.post("/api/v1/analyze", json=make_review_payload())
        data = response.json()
        assert "is_mock" in data, "Missing is_mock field"
        assert isinstance(data["is_mock"], bool)

    def test_analyze_returns_model_field(self, client):
        """Response must include model string field."""
        response = client.post("/api/v1/analyze", json=make_review_payload())
        data = response.json()
        assert "model" in data, "Missing model field"
        assert isinstance(data["model"], str)
        assert len(data["model"]) > 0

    def test_analyze_mock_mode_has_is_mock_true(self, client):
        """In mock mode, is_mock should be True and llm_mode should be 'mock'."""
        response = client.post("/api/v1/analyze", json=make_review_payload())
        data = response.json()
        assert data["is_mock"] is True
        assert data["llm_mode"] == "mock"
        assert data["model"] == "mock-rule-engine"


# ── Batch analyze endpoint ────────────────────────────────────────────────────

class TestAnalyzeBatchEndpoint:
    """Tests for POST /api/v1/analyze_batch."""

    @staticmethod
    def make_batch_payload(reviews: list[dict] | None = None) -> dict:
        """Build a valid batch request payload."""
        if reviews is None:
            reviews = [
                make_review_payload("r001", rating=2, review_text="Battery issue."),
                make_review_payload("r002", rating=4, review_text="Good value."),
                make_review_payload("r003", rating=1, review_text="Stopped working."),
            ]
        return {"reviews": reviews}

    def test_analyze_batch_returns_200(self, client):
        """POST /api/v1/analyze_batch should return HTTP 200."""
        response = client.post("/api/v1/analyze_batch", json=self.make_batch_payload())
        assert response.status_code == 200

    def test_analyze_batch_returns_total(self, client):
        """Response must include total count."""
        response = client.post("/api/v1/analyze_batch", json=self.make_batch_payload())
        data = response.json()
        assert data["total"] == 3

    def test_analyze_batch_returns_results(self, client):
        """Response must include results array."""
        response = client.post("/api/v1/analyze_batch", json=self.make_batch_payload())
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 3

    def test_analyze_batch_returns_needs_human_review_count(self, client):
        """Response must include needs_human_review_count."""
        response = client.post("/api/v1/analyze_batch", json=self.make_batch_payload())
        data = response.json()
        assert "needs_human_review_count" in data
        assert isinstance(data["needs_human_review_count"], int)

    def test_analyze_batch_results_match_input_order(self, client):
        """Results should preserve input order."""
        response = client.post("/api/v1/analyze_batch", json=self.make_batch_payload())
        data = response.json()
        result_ids = [r["review_id"] for r in data["results"]]
        assert result_ids == ["r001", "r002", "r003"]

    def test_analyze_batch_empty_reviews_returns_422(self, client):
        """Empty reviews list should return HTTP 422."""
        response = client.post("/api/v1/analyze_batch", json={"reviews": []})
        assert response.status_code == 422

    def test_analyze_batch_single_review(self, client):
        """Batch with a single review should work."""
        response = client.post(
            "/api/v1/analyze_batch",
            json={"reviews": [
                make_review_payload("r001", review_text="Single review test.")
            ]},
        )
        data = response.json()
        assert data["total"] == 1
        assert len(data["results"]) == 1

    # ── V2-M1: New batch response fields ──────────────────────────────────

    def test_analyze_batch_returns_real_count(self, client):
        """Batch response must include real_count field."""
        response = client.post("/api/v1/analyze_batch", json=self.make_batch_payload())
        data = response.json()
        assert "real_count" in data, "Missing real_count field"
        assert isinstance(data["real_count"], int)

    def test_analyze_batch_returns_mock_count(self, client):
        """Batch response must include mock_count field."""
        response = client.post("/api/v1/analyze_batch", json=self.make_batch_payload())
        data = response.json()
        assert "mock_count" in data, "Missing mock_count field"
        assert isinstance(data["mock_count"], int)

    def test_analyze_batch_returns_error_count(self, client):
        """Batch response must include error_count field."""
        response = client.post("/api/v1/analyze_batch", json=self.make_batch_payload())
        data = response.json()
        assert "error_count" in data, "Missing error_count field"
        assert isinstance(data["error_count"], int)

    def test_analyze_batch_mock_count_matches_total(self, client):
        """In mock mode, mock_count should equal total."""
        response = client.post("/api/v1/analyze_batch", json=self.make_batch_payload())
        data = response.json()
        assert data["mock_count"] == data["total"]
        assert data["real_count"] == 0


# ── Security: no sensitive data in responses ───────────────────────────────────

class TestSecurity:
    """Tests that responses do not leak sensitive data."""

    def test_health_does_not_leak_config(self, client):
        """Health response must not contain API keys or internal config."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert "api_key" not in str(data).lower()
        assert "secret" not in str(data).lower()

    def test_analyze_response_no_secrets(self, client):
        """Analyze response must not leak API keys, tokens, or env vars."""
        import json as _json
        response = client.post("/api/v1/analyze", json=make_review_payload())
        data = response.json()
        text = _json.dumps(data).lower()
        assert "sk-" not in text
        assert "bearer" not in text
        assert "deepseek_api_key" not in text

    def test_error_response_no_traceback(self, client):
        """Error responses must not include Python tracebacks."""
        # Trigger 422 with invalid rating
        response = client.post(
            "/api/v1/analyze",
            json=make_review_payload(rating=0),
        )
        data = response.json()
        text = str(data).lower()
        assert "traceback" not in text
        assert "file " not in text or '"file"' in text
