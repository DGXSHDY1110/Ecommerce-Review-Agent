"""Pydantic schemas for review input and AI analysis output.

V2-M1: Strict enum validation via Literal types, evidence tracking,
llm_mode/is_mock/model identification, and processing_time_ms.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ── Strict literal types (V2-M1: no more bare str) ──────────────────────────

Sentiment = Literal["positive", "neutral", "negative"]
IssueCategory = Literal[
    "logistics",
    "product_quality",
    "battery",
    "image_quality",
    "customer_service",
    "price",
    "description_mismatch",
    "other",
]
Priority = Literal["high", "medium", "low"]
ResponsibleTeam = Literal[
    "operations",
    "product",
    "supply_chain",
    "customer_service",
    "marketing",
    "unknown",
]
LlmMode = Literal["real", "mock"]

# ── Reference sets (kept for runtime membership checks if needed) ───────────

VALID_SENTIMENTS: set[str] = {"positive", "neutral", "negative"}
VALID_ISSUE_CATEGORIES: set[str] = {
    "logistics",
    "product_quality",
    "battery",
    "image_quality",
    "customer_service",
    "price",
    "description_mismatch",
    "other",
}
VALID_PRIORITIES: set[str] = {"high", "medium", "low"}
VALID_RESPONSIBLE_TEAMS: set[str] = {
    "operations",
    "product",
    "supply_chain",
    "customer_service",
    "marketing",
    "unknown",
}


class ReviewInput(BaseModel):
    """Input schema for a single review to be analyzed."""

    review_id: str = Field(..., min_length=1, description="Unique review identifier")
    platform: str = Field(..., min_length=1, description="E-commerce platform, e.g. Amazon, Shopify")
    product_name: str = Field(..., min_length=1, description="Name of the reviewed product")
    rating: int = Field(..., ge=1, le=5, description="Star rating from 1 to 5")
    review_text: str = Field(..., min_length=1, description="Full review text in original language")
    country: str = Field(..., min_length=1, description="Country code, e.g. US, DE, JP")
    created_at: str = Field(..., min_length=1, description="Review creation date, ISO format")

    @field_validator("review_text")
    @classmethod
    def review_text_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("review_text must not be empty or whitespace-only")
        return stripped


class ReviewAnalysis(BaseModel):
    """Output schema for a single analyzed review.

    V2-M1 changes:
    - sentiment / issue_category / priority / responsible_team are now strict Literal types.
    - Added evidence (list[str]), llm_mode, is_mock, model, processing_time_ms.
    - llm_mode and is_mock allow callers to distinguish real LLM from mock.
    """

    review_id: str = Field(..., min_length=1, description="Review identifier from input")

    sentiment: Sentiment = Field(default="neutral", description="Sentiment: positive, neutral, or negative")

    issue_category: IssueCategory = Field(
        default="other",
        description="Category: logistics, product_quality, battery, "
        "image_quality, customer_service, price, description_mismatch, other",
    )

    priority: Priority = Field(default="medium", description="Priority: high, medium, or low")

    responsible_team: ResponsibleTeam = Field(
        default="unknown",
        description="Team: operations, product, supply_chain, customer_service,"
        " marketing, unknown",
    )

    summary_zh: str = Field(default="", description="Chinese summary of the review issue")
    suggested_action_zh: str = Field(default="", description="Suggested action in Chinese")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    needs_human_review: bool = Field(default=True, description="Whether this result needs human review")

    # ── V2-M1 new fields ──────────────────────────────────────────────────
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence phrases extracted from the original review_text. "
        "Must be verbatim fragments — no fabrication. "
        "Empty list triggers needs_human_review via guardrails.",
    )
    llm_mode: LlmMode = Field(
        default="real",
        description="real = DeepSeek LLM output; mock = explicit mock/test path",
    )
    is_mock: bool = Field(
        default=False,
        description="True when llm_mode='mock'; False when llm_mode='real'",
    )
    model: str = Field(
        default="unknown",
        description="Model identifier: DEEPSEEK_MODEL for real, 'mock-rule-engine' for mock",
    )
    processing_time_ms: float | None = Field(
        default=None,
        description="Optional processing time in milliseconds (for real LLM calls)",
    )


class BatchAnalysisRequest(BaseModel):
    """Request body for batch review analysis."""

    reviews: list[ReviewInput] = Field(..., min_length=1, description="List of reviews to analyze")


class BatchAnalysisResponse(BaseModel):
    """Response body for batch review analysis.

    V2-M1: added error_count, real_count, mock_count for observability.
    """

    results: list[ReviewAnalysis] = Field(default_factory=list, description="List of analyzed reviews")
    total: int = Field(default=0, description="Total number of reviews analyzed")
    needs_human_review_count: int = Field(default=0, description="Number of reviews needing human review")
    error_count: int = Field(default=0, description="Number of reviews that hit errors (API, parse, validation)")
    real_count: int = Field(default=0, description="Number of reviews processed by real LLM")
    mock_count: int = Field(default=0, description="Number of reviews processed by mock engine")


# ── API schemas ────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """Request body for POST /api/v1/analyze."""

    review_id: str
    platform: str
    product_name: str
    rating: int = Field(..., ge=1, le=5)
    review_text: str = Field(..., min_length=1)
    country: str
    created_at: str


class AnalyzeResponse(BaseModel):
    """Response body for POST /api/v1/analyze.

    V2-M1: includes evidence, llm_mode, is_mock, model, processing_time_ms.
    """

    review_id: str
    sentiment: Sentiment
    issue_category: IssueCategory
    priority: Priority
    responsible_team: ResponsibleTeam
    summary_zh: str
    suggested_action_zh: str
    confidence: float
    needs_human_review: bool
    evidence: list[str] = Field(default_factory=list)
    llm_mode: LlmMode = "real"
    is_mock: bool = False
    model: str = "unknown"
    processing_time_ms: float | None = None


class HealthResponse(BaseModel):
    """Response body for GET /api/v1/health."""

    status: str
    service: str
