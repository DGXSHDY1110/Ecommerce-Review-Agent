"""Tests for Pydantic schemas — ReviewInput, ReviewAnalysis, batch models.

V2-M1: Added strict enum validation tests and new field tests.
"""

import pytest
from pydantic import ValidationError

from src.review_agent.schemas import (
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    ReviewAnalysis,
    ReviewInput,
)


class TestReviewInput:
    """Tests for ReviewInput model."""

    def test_valid_review_input(self):
        """ReviewInput should create successfully with valid data."""
        review = ReviewInput(
            review_id="r001",
            platform="Amazon",
            product_name="Test Product",
            rating=3,
            review_text="This is a test review.",
            country="US",
            created_at="2026-06-01",
        )
        assert review.review_id == "r001"
        assert review.rating == 3
        assert review.platform == "Amazon"

    def test_rating_below_1_raises_error(self):
        """rating < 1 should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewInput(
                review_id="r001",
                platform="Amazon",
                product_name="Test",
                rating=0,
                review_text="Bad.",
                country="US",
                created_at="2026-06-01",
            )

    def test_rating_above_5_raises_error(self):
        """rating > 5 should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewInput(
                review_id="r001",
                platform="Amazon",
                product_name="Test",
                rating=6,
                review_text="Great!",
                country="US",
                created_at="2026-06-01",
            )

    def test_rating_1_valid(self):
        """rating = 1 should be valid."""
        review = ReviewInput(
            review_id="r001",
            platform="Amazon",
            product_name="Test",
            rating=1,
            review_text="Terrible.",
            country="US",
            created_at="2026-06-01",
        )
        assert review.rating == 1

    def test_rating_5_valid(self):
        """rating = 5 should be valid."""
        review = ReviewInput(
            review_id="r001",
            platform="Amazon",
            product_name="Test",
            rating=5,
            review_text="Perfect!",
            country="US",
            created_at="2026-06-01",
        )
        assert review.rating == 5

    def test_empty_review_text_raises_error(self):
        """Empty review_text should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewInput(
                review_id="r001",
                platform="Amazon",
                product_name="Test",
                rating=3,
                review_text="",
                country="US",
                created_at="2026-06-01",
            )

    def test_whitespace_only_review_text_raises_error(self):
        """Whitespace-only review_text should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewInput(
                review_id="r001",
                platform="Amazon",
                product_name="Test",
                rating=3,
                review_text="   ",
                country="US",
                created_at="2026-06-01",
            )


class TestReviewAnalysis:
    """Tests for ReviewAnalysis model."""

    def test_default_values(self):
        """ReviewAnalysis should have sensible defaults."""
        analysis = ReviewAnalysis(review_id="r001")
        assert analysis.review_id == "r001"
        assert analysis.sentiment == "neutral"
        assert analysis.issue_category == "other"
        assert analysis.priority == "medium"
        assert analysis.responsible_team == "unknown"
        assert analysis.confidence == 0.0
        assert analysis.needs_human_review is True

    def test_confidence_range(self):
        """Confidence should be restricted to 0.0 - 1.0."""
        # Valid at 0.0
        a = ReviewAnalysis(review_id="r001", confidence=0.0)
        assert a.confidence == 0.0

        # Valid at 1.0
        b = ReviewAnalysis(review_id="r002", confidence=1.0)
        assert b.confidence == 1.0

    def test_confidence_below_0_raises_error(self):
        """Confidence < 0 should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewAnalysis(review_id="r001", confidence=-0.1)

    def test_confidence_above_1_raises_error(self):
        """Confidence > 1 should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewAnalysis(review_id="r001", confidence=1.1)

    def test_full_analysis_output(self):
        """ReviewAnalysis should accept all fields."""
        analysis = ReviewAnalysis(
            review_id="r001",
            sentiment="negative",
            issue_category="battery",
            priority="high",
            responsible_team="product",
            summary_zh="电池续航差。",
            suggested_action_zh="检查电池。",
            confidence=0.9,
            needs_human_review=False,
        )
        assert analysis.sentiment == "negative"
        assert analysis.issue_category == "battery"
        assert analysis.confidence == 0.9
        assert analysis.needs_human_review is False
        assert analysis.summary_zh == "电池续航差。"

    # ── V2-M1: Strict enum validation ──────────────────────────────────────

    def test_invalid_sentiment_raises_error(self):
        """Non-literal sentiment like 'angry' should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewAnalysis(review_id="r001", sentiment="angry")

    def test_invalid_issue_category_raises_error(self):
        """Non-literal issue_category like 'shipping' should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewAnalysis(review_id="r001", issue_category="shipping")

    def test_invalid_priority_raises_error(self):
        """Non-literal priority like 'urgent' should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewAnalysis(review_id="r001", priority="urgent")

    def test_invalid_responsible_team_raises_error(self):
        """Non-literal responsible_team like 'engineering' should raise ValidationError."""
        with pytest.raises(ValidationError):
            ReviewAnalysis(review_id="r001", responsible_team="engineering")

    def test_all_valid_sentiments_accepted(self):
        """All three valid sentiment values should be accepted."""
        for s in ("positive", "neutral", "negative"):
            analysis = ReviewAnalysis(review_id="r001", sentiment=s)
            assert analysis.sentiment == s

    def test_all_valid_priorities_accepted(self):
        """All three valid priority values should be accepted."""
        for p in ("high", "medium", "low"):
            analysis = ReviewAnalysis(review_id="r001", priority=p)
            assert analysis.priority == p

    # ── V2-M1: New fields ─────────────────────────────────────────────────

    def test_evidence_field_default(self):
        """evidence should default to empty list."""
        analysis = ReviewAnalysis(review_id="r001")
        assert analysis.evidence == []
        assert isinstance(analysis.evidence, list)

    def test_evidence_field_with_data(self):
        """evidence should accept list of strings."""
        analysis = ReviewAnalysis(
            review_id="r001",
            evidence=["Battery drains too fast", "night vision is blurry"],
        )
        assert len(analysis.evidence) == 2
        assert "Battery drains too fast" in analysis.evidence

    def test_llm_mode_field_default(self):
        """llm_mode should default to 'real'."""
        analysis = ReviewAnalysis(review_id="r001")
        assert analysis.llm_mode == "real"

    def test_llm_mode_only_accepts_real_or_mock(self):
        """llm_mode should only accept 'real' or 'mock'."""
        # Valid values
        for mode in ("real", "mock"):
            analysis = ReviewAnalysis(review_id="r001", llm_mode=mode)
            assert analysis.llm_mode == mode

        # Invalid value
        with pytest.raises(ValidationError):
            ReviewAnalysis(review_id="r001", llm_mode="fake")

    def test_is_mock_field_default(self):
        """is_mock should default to False."""
        analysis = ReviewAnalysis(review_id="r001")
        assert analysis.is_mock is False

    def test_is_mock_consistency_with_llm_mode(self):
        """is_mock should be consistent with llm_mode."""
        real_analysis = ReviewAnalysis(review_id="r001", llm_mode="real", is_mock=False)
        assert real_analysis.is_mock is False

        mock_analysis = ReviewAnalysis(review_id="r002", llm_mode="mock", is_mock=True)
        assert mock_analysis.is_mock is True

    def test_model_field_default(self):
        """model should default to 'unknown'."""
        analysis = ReviewAnalysis(review_id="r001")
        assert analysis.model == "unknown"

    def test_model_field_custom(self):
        """model should accept custom string values."""
        analysis = ReviewAnalysis(review_id="r001", model="deepseek-v4-pro")
        assert analysis.model == "deepseek-v4-pro"

    def test_processing_time_ms_field_default(self):
        """processing_time_ms should default to None."""
        analysis = ReviewAnalysis(review_id="r001")
        assert analysis.processing_time_ms is None

    def test_processing_time_ms_field_set(self):
        """processing_time_ms should accept float values."""
        analysis = ReviewAnalysis(review_id="r001", processing_time_ms=1234.5)
        assert analysis.processing_time_ms == 1234.5

    def test_v2_fields_in_full_output(self):
        """Full ReviewAnalysis should include all V2-M1 fields."""
        analysis = ReviewAnalysis(
            review_id="r001",
            sentiment="negative",
            issue_category="battery",
            priority="high",
            responsible_team="product",
            summary_zh="电池问题。",
            suggested_action_zh="检查电池。",
            confidence=0.9,
            needs_human_review=False,
            evidence=["battery drains"],
            llm_mode="real",
            is_mock=False,
            model="deepseek-v4-pro",
            processing_time_ms=500.0,
        )
        assert analysis.evidence == ["battery drains"]
        assert analysis.llm_mode == "real"
        assert analysis.is_mock is False
        assert analysis.model == "deepseek-v4-pro"
        assert analysis.processing_time_ms == 500.0


class TestBatchModels:
    """Tests for BatchAnalysisRequest and BatchAnalysisResponse."""

    def test_batch_request_valid(self):
        """BatchAnalysisRequest should accept a list of reviews."""
        reviews = [
            ReviewInput(
                review_id="r001",
                platform="Amazon",
                product_name="P1",
                rating=2,
                review_text="Bad battery.",
                country="US",
                created_at="2026-06-01",
            ),
            ReviewInput(
                review_id="r002",
                platform="Shopify",
                product_name="P2",
                rating=5,
                review_text="Great product!",
                country="DE",
                created_at="2026-06-02",
            ),
        ]
        request = BatchAnalysisRequest(reviews=reviews)
        assert len(request.reviews) == 2
        assert request.reviews[0].review_id == "r001"

    def test_batch_request_empty_list_raises_error(self):
        """Empty reviews list should raise ValidationError."""
        with pytest.raises(ValidationError):
            BatchAnalysisRequest(reviews=[])

    def test_batch_response(self):
        """BatchAnalysisResponse should hold results and summary counts."""
        results = [
            ReviewAnalysis(review_id="r001", needs_human_review=True),
            ReviewAnalysis(review_id="r002", needs_human_review=False),
        ]
        response = BatchAnalysisResponse(
            results=results,
            total=2,
            needs_human_review_count=1,
        )
        assert response.total == 2
        assert response.needs_human_review_count == 1
        assert len(response.results) == 2

    # ── V2-M1: New batch fields ───────────────────────────────────────────

    def test_batch_response_error_count_default(self):
        """error_count should default to 0."""
        response = BatchAnalysisResponse()
        assert response.error_count == 0

    def test_batch_response_real_count_default(self):
        """real_count should default to 0."""
        response = BatchAnalysisResponse()
        assert response.real_count == 0

    def test_batch_response_mock_count_default(self):
        """mock_count should default to 0."""
        response = BatchAnalysisResponse()
        assert response.mock_count == 0

    def test_batch_response_with_v2_counts(self):
        """BatchAnalysisResponse should accept V2-M1 count fields."""
        response = BatchAnalysisResponse(
            results=[ReviewAnalysis(review_id="r001")],
            total=1,
            needs_human_review_count=1,
            error_count=1,
            real_count=0,
            mock_count=1,
        )
        assert response.error_count == 1
        assert response.real_count == 0
        assert response.mock_count == 1
