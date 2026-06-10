"""Tests for the review_agent package skeleton.

Milestone 1+2: verify package imports, schemas, config, and mock LLM client.
"""

import pytest
from fastapi.testclient import TestClient


def test_package_import():
    """Verify the review_agent package can be imported."""
    import review_agent
    assert review_agent.__version__ == "0.1.0"


def test_schemas_import():
    """Verify schemas module can be imported."""
    from review_agent.schemas import HealthResponse, ReviewInput, ReviewAnalysis

    # Verify HealthResponse works
    health = HealthResponse(status="ok", service="ecommerce-review-agent")
    assert health.status == "ok"
    assert health.service == "ecommerce-review-agent"

    # Verify ReviewInput validation works
    review = ReviewInput(
        review_id="r001",
        platform="Amazon",
        product_name="Test Product",
        rating=2,
        review_text="Not great.",
        country="US",
        created_at="2026-06-01",
    )
    assert review.review_id == "r001"
    assert review.rating == 2

    # Verify ReviewAnalysis works
    analysis = ReviewAnalysis(
        review_id="r001",
        sentiment="negative",
        issue_category="product_quality",
        priority="high",
        responsible_team="product",
        summary_zh="测试。",
        suggested_action_zh="建议测试。",
        confidence=0.9,
        needs_human_review=False,
    )
    assert analysis.review_id == "r001"
    assert analysis.confidence == 0.9


def test_config_import():
    """Verify config module can be imported with default settings."""
    from review_agent.config import settings

    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 8000
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_model == "deepseek-v4-pro"


def test_llm_client_import():
    """Verify llm_client module with mock mode works."""
    from review_agent.llm_client import LLMClient
    from review_agent.config import Settings

    mock_settings = Settings()
    mock_settings.llm_mock_mode = True
    client = LLMClient(settings=mock_settings)
    assert client.model == "deepseek-v4-pro"
    assert client.mock_mode is True


def test_workflow_import():
    """Verify workflow module functions are importable."""
    from review_agent.workflow import analyze_review, analyze_reviews_batch, analyze_batch_request
    assert callable(analyze_review)
    assert callable(analyze_reviews_batch)
    assert callable(analyze_batch_request)


def test_report_import():
    """Verify report module generates markdown."""
    from review_agent.report import generate_daily_report
    report = generate_daily_report([])
    assert "每日评论分析报告" in report
    assert "暂无数据" in report


class TestHealthEndpoint:
    """Test the FastAPI health check endpoint."""

    @pytest.fixture
    def client(self):
        from review_agent.api import app
        return TestClient(app)

    def test_health_returns_200(self, client):
        """GET /api/v1/health returns HTTP 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_returns_service_name(self, client):
        """GET /api/v1/health returns service=ecommerce-review-agent."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "ecommerce-review-agent"

    def test_health_response_schema(self, client):
        """GET /api/v1/health response matches HealthResponse schema."""
        response = client.get("/api/v1/health")
        data = response.json()
        assert set(data.keys()) == {"status", "service"}
