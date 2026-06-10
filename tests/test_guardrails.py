"""Tests for guardrail rules in the workflow layer.

Tests each guardrail rule in isolation — these tests do NOT call any
external API.  They verify deterministic post-hoc rules only.
"""

import pytest

from src.review_agent.schemas import ReviewAnalysis, ReviewInput
from src.review_agent.workflow import apply_guardrails


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_review(
    review_id: str = "r001",
    rating: int = 2,
    review_text: str = "Bad product.",
) -> ReviewInput:
    """Create a minimal ReviewInput for guardrail testing."""
    return ReviewInput(
        review_id=review_id,
        platform="Amazon",
        product_name="Test Product",
        rating=rating,
        review_text=review_text,
        country="US",
        created_at="2026-06-01",
    )


def make_analysis(
    review_id: str = "r001",
    sentiment: str = "negative",
    issue_category: str = "product_quality",
    priority: str = "high",
    responsible_team: str = "product",
    summary_zh: str = "测试摘要。",
    suggested_action_zh: str = "测试建议。",
    confidence: float = 0.9,
    needs_human_review: bool = False,
    evidence: list[str] | None = None,
) -> ReviewAnalysis:
    """Create a ReviewAnalysis with specified fields.

    V2-M1: evidence defaults to a non-empty list so existing tests that expect
    guardrails to pass still work.  Explicit evidence=[] triggers the new
    empty-evidence guardrail.
    """
    if evidence is None:
        evidence = ["test evidence phrase from review"]
    return ReviewAnalysis(
        review_id=review_id,
        sentiment=sentiment,
        issue_category=issue_category,
        priority=priority,
        responsible_team=responsible_team,
        summary_zh=summary_zh,
        suggested_action_zh=suggested_action_zh,
        confidence=confidence,
        needs_human_review=needs_human_review,
        evidence=evidence,
    )


# ── Rule 1: Low confidence ─────────────────────────────────────────────────────

class TestLowConfidenceGuardrail:
    """confidence < threshold → needs_human_review = True."""

    def test_confidence_below_default_threshold_flags(self):
        """0.5 < 0.6 → needs_human_review becomes True."""
        review = make_review(rating=4)
        analysis = make_analysis(confidence=0.5, needs_human_review=False)
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_confidence_at_threshold_passes(self):
        """0.6 >= 0.6 → needs_human_review unchanged (if originally False)."""
        review = make_review(rating=4)
        analysis = make_analysis(confidence=0.6, needs_human_review=False)
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is False

    def test_confidence_above_threshold_passes(self):
        """0.9 >= 0.6 → needs_human_review unchanged."""
        review = make_review(rating=4)
        analysis = make_analysis(confidence=0.9, needs_human_review=False)
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is False

    def test_custom_threshold(self):
        """With threshold=0.8, confidence=0.75 should trigger."""
        review = make_review(rating=4)
        analysis = make_analysis(confidence=0.75, needs_human_review=False)
        result = apply_guardrails(review, analysis, confidence_threshold=0.8)
        assert result.needs_human_review is True


# ── Rule 2: Rating/sentiment contradiction ──────────────────────────────────────

class TestContradictionGuardrail:
    """rating <= 2 AND sentiment != negative → needs_human_review = True."""

    def test_low_rating_positive_sentiment_flags(self):
        """rating=1 + sentiment=positive → contradiction → flagged."""
        review = make_review(rating=1, review_text="Love it!")
        analysis = make_analysis(
            sentiment="positive",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_low_rating_neutral_sentiment_flags(self):
        """rating=2 + sentiment=neutral → contradiction → flagged."""
        review = make_review(rating=2)
        analysis = make_analysis(
            sentiment="neutral",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_low_rating_negative_sentiment_passes(self):
        """rating=1 + sentiment=negative → consistent → not flagged by this rule."""
        review = make_review(rating=1)
        analysis = make_analysis(
            sentiment="negative",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        # May still be flagged by other rules (e.g. low confidence),
        # but this rule should not be the trigger.  Since confidence is 0.9
        # and category is product_quality (not "other"), result should
        # keep needs_human_review=False.
        assert result.needs_human_review is False

    def test_high_rating_negative_sentiment_not_flagged_by_this_rule(self):
        """rating=5 + sentiment=negative → this rule only checks rating<=2."""
        review = make_review(rating=5, review_text="Terrible!")
        analysis = make_analysis(
            sentiment="negative",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        # Rating > 2 so rule 2 doesn't apply; confidence is 0.9 so rule 1
        # doesn't apply; and category is product_quality not "other".
        assert result.needs_human_review is False


# ── Rule 3: "other" category + low rating ───────────────────────────────────────

class TestOtherCategoryGuardrail:
    """issue_category == "other" AND rating <= 2 → needs_human_review = True."""

    def test_other_with_low_rating_flags(self):
        """other + rating=2 → flagged."""
        review = make_review(rating=2)
        analysis = make_analysis(
            issue_category="other",
            sentiment="negative",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_other_with_rating_1_flags(self):
        """other + rating=1 → flagged."""
        review = make_review(rating=1)
        analysis = make_analysis(
            issue_category="other",
            sentiment="negative",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_other_with_rating_3_passes(self):
        """other + rating=3 → not flagged by this rule alone."""
        review = make_review(rating=3)
        analysis = make_analysis(
            issue_category="other",
            sentiment="neutral",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        # Rule 3 only triggers for rating <= 2.  But confidence=0.9 and
        # sentiment=neutral with rating=3 is fine for rule 2.
        assert result.needs_human_review is False

    def test_other_with_rating_5_passes(self):
        """other + rating=5 → not flagged by this rule."""
        review = make_review(rating=5)
        analysis = make_analysis(
            issue_category="other",
            sentiment="positive",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is False


# ── Rule 4: Empty Chinese summaries ─────────────────────────────────────────────

class TestEmptySummaryGuardrail:
    """Empty summary_zh or suggested_action_zh → needs_human_review = True."""

    def test_empty_summary_flags(self):
        """summary_zh="" → flagged."""
        review = make_review(rating=4)
        analysis = make_analysis(
            summary_zh="",
            suggested_action_zh="有效建议。",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_empty_action_flags(self):
        """suggested_action_zh="" → flagged."""
        review = make_review(rating=4)
        analysis = make_analysis(
            summary_zh="有效摘要。",
            suggested_action_zh="",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_both_empty_flags(self):
        """Both empty → flagged."""
        review = make_review(rating=4)
        analysis = make_analysis(
            summary_zh="",
            suggested_action_zh="",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_whitespace_only_summary_flags(self):
        """summary_zh with only spaces → flagged as empty."""
        review = make_review(rating=4)
        analysis = make_analysis(
            summary_zh="   ",
            suggested_action_zh="有效建议。",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_both_filled_passes(self):
        """Both fields present → not flagged by this rule."""
        review = make_review(rating=4)
        analysis = make_analysis(
            summary_zh="有效的摘要。",
            suggested_action_zh="有效的建议。",
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is False


# ── Combined guardrail scenarios ────────────────────────────────────────────────

class TestCombinedGuardrails:
    """Test scenarios where multiple guardrails fire simultaneously."""

    def test_low_confidence_plus_contradiction(self):
        """Multiple rules can trigger on the same review."""
        review = make_review(rating=2)
        analysis = make_analysis(
            sentiment="positive",  # triggers rule 2
            confidence=0.3,         # triggers rule 1
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_all_clear_scenario(self):
        """A perfectly normal review should pass all guardrails."""
        review = make_review(rating=1, review_text="Battery exploded.")
        analysis = make_analysis(
            sentiment="negative",
            issue_category="battery",
            priority="high",
            summary_zh="电池爆炸。",
            suggested_action_zh="立即检查。",
            confidence=0.95,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is False

    def test_guardrail_does_not_mutate_input_review(self):
        """apply_guardrails should not modify the input ReviewInput."""
        review = make_review(rating=2)
        original_rating = review.rating
        analysis = make_analysis(
            sentiment="positive",
            confidence=0.5,
            needs_human_review=False,
        )
        apply_guardrails(review, analysis)
        assert review.rating == original_rating

    def test_high_priority_keeps_existing_flag(self):
        """High priority with existing needs_human_review=True stays True."""
        review = make_review(rating=1)
        analysis = make_analysis(
            sentiment="negative",
            priority="high",
            confidence=0.9,
            needs_human_review=True,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True


# ── Rule 6 (V2-M1): Empty evidence ────────────────────────────────────────────

class TestEvidenceGuardrail:
    """Empty evidence → needs_human_review = True."""

    def test_empty_evidence_flags(self):
        """evidence=[] → flagged for human review."""
        review = make_review(rating=4)
        analysis = make_analysis(
            evidence=[],
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True

    def test_non_empty_evidence_passes(self):
        """evidence with content → not flagged by this rule."""
        review = make_review(rating=4)
        analysis = make_analysis(
            evidence=["battery drains fast"],
            confidence=0.9,
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is False

    def test_empty_evidence_with_other_issues(self):
        """Empty evidence combined with other guardrail triggers."""
        review = make_review(rating=2)
        analysis = make_analysis(
            evidence=[],
            confidence=0.5,  # also triggers low confidence
            needs_human_review=False,
        )
        result = apply_guardrails(review, analysis)
        assert result.needs_human_review is True
