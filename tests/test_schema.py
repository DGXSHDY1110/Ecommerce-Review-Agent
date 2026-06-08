"""Tests for Pydantic schemas — ReviewInput, ReviewAnalysis, batch models."""

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
