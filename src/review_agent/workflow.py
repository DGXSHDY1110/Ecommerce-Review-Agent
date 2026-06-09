"""Review analysis workflow orchestration.

Coordinates the steps: read reviews → call LLM → apply guardrails → return results.

This module is the **Agentic Workflow** layer: it wires together the LLM client
and the deterministic guardrail rules, but does NOT make HTTP calls or contain
business logic itself.  Each function is a pure orchestrator.
"""

import logging
from typing import Optional

from .config import Settings, get_settings
from .llm_client import LLMClient, get_client
from .schemas import (
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    ReviewAnalysis,
    ReviewInput,
)
from .utils import log_error_case

logger = logging.getLogger(__name__)


# ── Guardrails ─────────────────────────────────────────────────────────────────

def apply_guardrails(
    review: ReviewInput,
    analysis: ReviewAnalysis,
    confidence_threshold: Optional[float] = None,
) -> ReviewAnalysis:
    """Apply post-hoc guardrail rules to an analysis result.

    These rules are **deterministic** — they do not call any external service.
    They act as a safety net that catches cases the LLM might get wrong or
    express low confidence about.

    Rules (applied in order):

    1. **Low confidence** — if ``confidence < threshold``, flag for human review.
    2. **Rating/sentiment contradiction** — if ``rating <= 2`` but sentiment is
       not ``negative``, flag for human review.
    3. **Uncertain category with low rating** — if ``issue_category == "other"``
       AND ``rating <= 2``, flag for human review.
    4. **Missing Chinese summaries** — if ``summary_zh`` or ``suggested_action_zh``
       is empty / whitespace-only, flag for human review.
    5. **High priority** — high-priority results keep their existing
       ``needs_human_review`` state, but we log a note encouraging manual
       verification.

    Args:
        review:              The original review input.
        analysis:            The LLM-produced (or mock) analysis result.
        confidence_threshold: Override the confidence threshold from config.
                              Defaults to ``Settings.confidence_threshold`` (0.6).

    Returns:
        The same ``ReviewAnalysis`` instance, mutated in-place with
        ``needs_human_review`` potentially set to ``True``.
    """
    if confidence_threshold is None:
        settings = get_settings()
        confidence_threshold = settings.confidence_threshold

    triggered_rules: list[str] = []

    # ── Rule 1: Low confidence ───────────────────────────────────────────
    if analysis.confidence < confidence_threshold:
        if not analysis.needs_human_review:
            analysis.needs_human_review = True
            triggered_rules.append("low_confidence")

    # ── Rule 2: Rating / sentiment contradiction ─────────────────────────
    if review.rating <= 2 and analysis.sentiment != "negative":
        if not analysis.needs_human_review:
            analysis.needs_human_review = True
        triggered_rules.append("rating_sentiment_contradiction")

    # ── Rule 3: "other" category with low rating ─────────────────────────
    if analysis.issue_category == "other" and review.rating <= 2:
        if not analysis.needs_human_review:
            analysis.needs_human_review = True
        triggered_rules.append("other_category_low_rating")

    # ── Rule 4: Empty Chinese summaries ──────────────────────────────────
    summary_empty = not (analysis.summary_zh or "").strip()
    action_empty = not (analysis.suggested_action_zh or "").strip()
    if summary_empty or action_empty:
        if not analysis.needs_human_review:
            analysis.needs_human_review = True
        if summary_empty and action_empty:
            triggered_rules.append("empty_summary_and_action")
        elif summary_empty:
            triggered_rules.append("empty_summary")
        else:
            triggered_rules.append("empty_suggested_action")

    # ── Rule 5: High priority — log and preserve existing flag ────────────
    if analysis.priority == "high":
        triggered_rules.append("high_priority_noted")
        # We keep the existing needs_human_review state; the other rules may
        # have already set it.  Just log for observability.
        logger.info(
            "High-priority review %s (category=%s, confidence=%.2f) — "
            "needs_human_review=%s",
            analysis.review_id,
            analysis.issue_category,
            analysis.confidence,
            analysis.needs_human_review,
        )

    # ── Log guardrail triggers to error_cases.jsonl ──────────────────────
    if triggered_rules:
        logger.info(
            "Guardrails triggered for review %s: %s",
            analysis.review_id, ", ".join(triggered_rules),
        )
        # Only log to error_cases when human review is actually required
        if analysis.needs_human_review:
            log_error_case(
                review_id=analysis.review_id,
                error_type="GUARDRAIL_TRIGGERED",
                error_message=f"Rules: {', '.join(triggered_rules)}",
                fallback_used=False,
                needs_human_review=True,
            )

    return analysis


# Keep the internal alias for backward compatibility in existing code
_apply_guardrails = apply_guardrails


# ── Public orchestration API ───────────────────────────────────────────────────

def analyze_review(
    review: ReviewInput,
    client: Optional[LLMClient] = None,
) -> ReviewAnalysis:
    """Analyze a single review through the full pipeline.

    Pipeline:  LLM classify → apply guardrails → return result.

    Args:
        review: The review input to analyze.
        client: Optional LLMClient instance (uses default if not provided).

    Returns:
        ReviewAnalysis with guardrails applied.
    """
    if client is None:
        client = get_client()

    analysis = client.analyze_review(review)
    analysis = apply_guardrails(review, analysis)
    return analysis


def analyze_reviews_batch(
    reviews: list[ReviewInput],
    client: Optional[LLMClient] = None,
) -> list[ReviewAnalysis]:
    """Analyze a list of reviews sequentially.

    Each review is processed independently through the full pipeline.
    If one review fails, a safe fallback is substituted and processing
    continues with the remaining reviews.

    Args:
        reviews: List of review inputs to analyze.
        client:  Optional LLMClient instance (uses default if not provided).

    Returns:
        List of ReviewAnalysis results (same order as input).
    """
    if client is None:
        client = get_client()

    results: list[ReviewAnalysis] = []
    for review in reviews:
        try:
            result = analyze_review(review, client=client)
            results.append(result)
        except Exception as exc:
            logger.error("Unhandled exception analyzing review %s: %s",
                         review.review_id, exc)
            # Log to error cases and append a safe fallback
            log_error_case(
                review_id=review.review_id,
                error_type="UNHANDLED_EXCEPTION",
                error_message=str(exc)[:500],
                fallback_used=True,
                needs_human_review=True,
            )
            results.append(
                ReviewAnalysis(
                    review_id=review.review_id,
                    sentiment="neutral",
                    issue_category="other",
                    priority="medium",
                    responsible_team="unknown",
                    summary_zh="分析过程发生异常，需要人工复核。",
                    suggested_action_zh="请人工查看该评论并确认分类结果。",
                    confidence=0.0,
                    needs_human_review=True,
                )
            )
    return results


def analyze_batch_request(
    request: BatchAnalysisRequest,
    client: Optional[LLMClient] = None,
) -> BatchAnalysisResponse:
    """Analyze a BatchAnalysisRequest and return a BatchAnalysisResponse.

    Args:
        request: Batch analysis request containing reviews.
        client:  Optional LLMClient instance (uses default if not provided).

    Returns:
        BatchAnalysisResponse with results and summary counts.
    """
    results = analyze_reviews_batch(request.reviews, client=client)
    needs_human_review_count = sum(1 for r in results if r.needs_human_review)

    return BatchAnalysisResponse(
        results=results,
        total=len(results),
        needs_human_review_count=needs_human_review_count,
    )
