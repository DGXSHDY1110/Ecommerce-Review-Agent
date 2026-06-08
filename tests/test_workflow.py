"""Tests for workflow orchestration with mock LLM client.

Never calls a real API — uses mock mode exclusively.
"""

import pytest

from src.review_agent.config import Settings, get_settings
from src.review_agent.llm_client import LLMClient
from src.review_agent.schemas import (
    BatchAnalysisRequest,
    ReviewAnalysis,
    ReviewInput,
)
from src.review_agent.workflow import (
    analyze_batch_request,
    analyze_review,
    analyze_reviews_batch,
    _apply_guardrails,
)


def make_review(review_id="r001", rating=2, review_text="Bad product.") -> ReviewInput:
    """Helper to create a minimal ReviewInput."""
    return ReviewInput(
        review_id=review_id,
        platform="Amazon",
        product_name="Test Product",
        rating=rating,
        review_text=review_text,
        country="US",
        created_at="2026-06-01",
    )


def make_mock_settings() -> Settings:
    """Return Settings with mock mode enabled."""
    settings = get_settings()
    settings.llm_mock_mode = True
    return settings


class TestAnalyzeReview:
    """Tests for analyze_review with mock mode."""

    def test_analyze_review_returns_review_analysis(self):
        """analyze_review should return a ReviewAnalysis instance."""
        settings = make_mock_settings()
        client = LLMClient(settings=settings)
        review = make_review()
        result = analyze_review(review, client=client)
        assert isinstance(result, ReviewAnalysis)
        assert result.review_id == "r001"

    def test_low_rating_triggers_human_review(self):
        """Rating <= 2 should have needs_human_review=True in mock mode."""
        settings = make_mock_settings()
        client = LLMClient(settings=settings)
        review = make_review(rating=1)
        result = analyze_review(review, client=client)
        assert result.needs_human_review is True

    def test_high_rating_still_needs_review_in_mock(self):
        """In mock mode, even high ratings get human review flagged (confidence = 0.5)."""
        settings = make_mock_settings()
        client = LLMClient(settings=settings)
        review = make_review(rating=5, review_text="Love it!")
        result = analyze_review(review, client=client)
        # Mock confidence is 0.5 < 0.6, so needs_human_review=True
        assert result.needs_human_review is True

    def test_battery_keyword_detected(self):
        """Mock mode should detect battery keywords."""
        settings = make_mock_settings()
        client = LLMClient(settings=settings)
        review = make_review(rating=2, review_text="Battery drains too fast.")
        result = analyze_review(review, client=client)
        assert result.issue_category == "battery"

    def test_logistics_keyword_detected(self):
        """Mock mode should detect logistics keywords."""
        settings = make_mock_settings()
        client = LLMClient(settings=settings)
        review = make_review(rating=3, review_text="Shipping was very slow.")
        result = analyze_review(review, client=client)
        assert result.issue_category == "logistics"


class TestGuardrails:
    """Tests for _apply_guardrails post-hoc rules."""

    def test_low_confidence_flags_human_review(self):
        """Confidence < 0.6 should set needs_human_review=True."""
        review = make_review(rating=4)
        analysis = ReviewAnalysis(
            review_id="r001",
            sentiment="positive",
            confidence=0.5,
            needs_human_review=False,
        )
        result = _apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_contradiction_detection(self):
        """rating <= 2 + non-negative sentiment → needs_human_review=True."""
        review = make_review(rating=1)
        analysis = ReviewAnalysis(
            review_id="r001",
            sentiment="positive",
            confidence=0.9,
            needs_human_review=False,
        )
        result = _apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_other_category_low_rating_flags(self):
        """issue_category=other + rating <= 2 → needs_human_review=True."""
        review = make_review(rating=2)
        analysis = ReviewAnalysis(
            review_id="r001",
            sentiment="negative",
            issue_category="other",
            confidence=0.9,
            needs_human_review=False,
        )
        result = _apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_valid_result_passes_guardrails(self):
        """High-confidence, consistent result should keep original flags."""
        review = make_review(rating=1, review_text="Product broke immediately.")
        analysis = ReviewAnalysis(
            review_id="r001",
            sentiment="negative",
            issue_category="product_quality",
            confidence=0.9,
            needs_human_review=False,
        )
        result = _apply_guardrails(review, analysis)
        # Still false because confidence >= 0.6, sentiment matches rating, category is not "other"
        assert result.needs_human_review is False


class TestAnalyzeBatch:
    """Tests for batch analysis functions."""

    def test_analyze_reviews_batch(self):
        """analyze_reviews_batch should return a list of same length."""
        settings = make_mock_settings()
        client = LLMClient(settings=settings)
        reviews = [
            make_review("r001"),
            make_review("r002"),
            make_review("r003"),
        ]
        results = analyze_reviews_batch(reviews, client=client)
        assert len(results) == 3
        assert all(isinstance(r, ReviewAnalysis) for r in results)
        assert [r.review_id for r in results] == ["r001", "r002", "r003"]

    def test_analyze_batch_request(self):
        """analyze_batch_request should return BatchAnalysisResponse."""
        settings = make_mock_settings()
        client = LLMClient(settings=settings)
        reviews = [
            make_review("r001", rating=1),
            make_review("r002", rating=5),
        ]
        request = BatchAnalysisRequest(reviews=reviews)
        response = analyze_batch_request(request, client=client)
        assert response.total == 2
        assert response.needs_human_review_count >= 0
        assert len(response.results) == 2
