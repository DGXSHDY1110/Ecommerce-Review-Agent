"""Review analysis workflow orchestration.

Coordinates the steps: read reviews → call LLM → apply guardrails → return results.
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

logger = logging.getLogger(__name__)


def _apply_guardrails(review: ReviewInput, analysis: ReviewAnalysis) -> ReviewAnalysis:
    """Apply post-hoc guardrail rules to an analysis result.

    Rules:
    1. confidence < threshold → needs_human_review = True
    2. rating <= 2 but sentiment != negative → needs_human_review = True
    3. issue_category == other and rating <= 2 → needs_human_review = True
    """
    # Rule 1: low confidence
    if analysis.confidence < 0.6:
        analysis.needs_human_review = True

    # Rule 2: contradiction — low rating but non-negative sentiment
    if review.rating <= 2 and analysis.sentiment != "negative":
        analysis.needs_human_review = True
        logger.info(
            "Guardrail: review %s has rating=%d but sentiment=%s — flagging for human review",
            review.review_id,
            review.rating,
            analysis.sentiment,
        )

    # Rule 3: other category with low rating
    if analysis.issue_category == "other" and review.rating <= 2:
        analysis.needs_human_review = True
        logger.info(
            "Guardrail: review %s has rating=%d and issue_category=other — flagging for human review",
            review.review_id,
            review.rating,
        )

    return analysis


def analyze_review(
    review: ReviewInput,
    client: Optional[LLMClient] = None,
) -> ReviewAnalysis:
    """Analyze a single review.

    Args:
        review: The review input to analyze.
        client: Optional LLMClient instance (uses default if not provided).

    Returns:
        ReviewAnalysis with guardrails applied.
    """
    if client is None:
        client = get_client()

    analysis = client.analyze_review(review)
    analysis = _apply_guardrails(review, analysis)
    return analysis


def analyze_reviews_batch(
    reviews: list[ReviewInput],
    client: Optional[LLMClient] = None,
) -> list[ReviewAnalysis]:
    """Analyze a list of reviews.

    Args:
        reviews: List of review inputs to analyze.
        client: Optional LLMClient instance (uses default if not provided).

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
            logger.error("Failed to analyze review %s: %s", review.review_id, exc)
            # Append a safe fallback
            results.append(
                ReviewAnalysis(
                    review_id=review.review_id,
                    sentiment="neutral",
                    issue_category="other",
                    priority="medium",
                    responsible_team="unknown",
                    summary_zh="分析过程异常，需要人工复核。",
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
        client: Optional LLMClient instance (uses default if not provided).

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
