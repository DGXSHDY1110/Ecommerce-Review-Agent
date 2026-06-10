"""FastAPI application for the ecommerce review agent service.

Exposes REST endpoints for review classification, designed to be called
by n8n HTTP Request nodes and other HTTP clients.

V2-M4: Added GET /api/v1/mode for service mode introspection.
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .config import settings
from .schemas import (
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    HealthResponse,
    ReviewAnalysis,
    ReviewInput,
)
from .workflow import analyze_batch_request, analyze_review

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ecommerce Review Agent",
    description="AI-powered cross-border e-commerce review monitoring and classification service",
    version="0.1.0",
)


# ── Mode response schema ──────────────────────────────────────────────────────

class ModeResponse(BaseModel):
    """Response body for GET /api/v1/mode."""

    service: str = Field(default="ecommerce-review-agent")
    use_mock_llm: bool = Field(description="Whether mock LLM mode is enabled")
    llm_mode: str = Field(description="Current LLM mode: 'real' or 'mock'")
    model: str = Field(description="Configured DeepSeek model name")
    base_url: str = Field(description="DeepSeek API base URL")
    api_key_configured: bool = Field(description="Whether DEEPSEEK_API_KEY is set (NOT the key itself)")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Return service health status."""
    return HealthResponse(status="ok", service="ecommerce-review-agent")


# ── Service mode ──────────────────────────────────────────────────────────────

@app.get("/api/v1/mode", response_model=ModeResponse)
async def service_mode():
    """Return the current service mode and configuration.

    Does NOT return the API key — only whether it is configured.
    n8n and other clients can use this to decide how to handle results
    (e.g., if is_mock=true, results should not be used for business decisions).
    """
    return ModeResponse(
        service="ecommerce-review-agent",
        use_mock_llm=settings.llm_mock_mode,
        llm_mode="mock" if settings.llm_mock_mode else "real",
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        api_key_configured=bool(settings.deepseek_api_key),
    )


# ── Single review analysis ────────────────────────────────────────────────────

@app.post("/api/v1/analyze", response_model=ReviewAnalysis)
async def analyze_single(review: ReviewInput):
    """Analyze a single e-commerce review.

    Accepts a review with platform, product, rating, review_text, country, and
    created_at.  Returns a structured classification including sentiment, issue
    category, priority, responsible team, Chinese summaries, confidence score,
    and a human-review flag.

    The endpoint delegates to the shared workflow layer — no business logic
    lives directly inside the route handler.
    """
    try:
        result = analyze_review(review)
        return result
    except Exception as exc:
        logger.error("Unhandled error in /api/v1/analyze for review %s: %s",
                     review.review_id, exc)
        raise HTTPException(
            status_code=500,
            detail="Internal analysis error. The service logged the failure; please retry later.",
        )


# ── Batch review analysis ─────────────────────────────────────────────────────

@app.post("/api/v1/analyze_batch", response_model=BatchAnalysisResponse)
async def analyze_batch(request: BatchAnalysisRequest):
    """Analyze a batch of e-commerce reviews.

    Accepts a list of reviews and returns a structured classification for each,
    together with summary counts (total, needs_human_review_count).

    Each individual review is processed through the same analysis pipeline used
    by the single-review endpoint.
    """
    try:
        result = analyze_batch_request(request)
        return result
    except Exception as exc:
        logger.error("Unhandled error in /api/v1/analyze_batch: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Internal batch analysis error. The service logged the failure; please retry later.",
        )


# ── Global exception handler (safety net) ─────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all handler that prevents tracebacks from leaking to clients."""
    logger.error("Unhandled exception on %s %s: %s",
                 request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Unexpected server error. Please contact the service owner."},
    )
