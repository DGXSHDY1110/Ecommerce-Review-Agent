"""Pydantic schemas for review input and AI analysis output."""

from pydantic import BaseModel, Field, field_validator

# ── Enums for reference (validated via Literal alternatives in Pydantic) ──────
VALID_SENTIMENTS = {"positive", "neutral", "negative"}
VALID_ISSUE_CATEGORIES = {
    "logistics",
    "product_quality",
    "battery",
    "image_quality",
    "customer_service",
    "price",
    "description_mismatch",
    "other",
}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_RESPONSIBLE_TEAMS = {
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
    """Output schema for a single analyzed review."""

    review_id: str = Field(..., min_length=1, description="Review identifier from input")
    sentiment: str = Field(default="neutral", description="Sentiment: positive, neutral, or negative")
    issue_category: str = Field(
        default="other",
        description="Category: logistics, product_quality, battery, "
        "image_quality, customer_service, price, description_mismatch, other",
    )
    priority: str = Field(default="medium", description="Priority: high, medium, or low")
    responsible_team: str = Field(
        default="unknown",
        description="Team: operations, product, supply_chain, customer_service,"
        " marketing, unknown",
    )
    summary_zh: str = Field(default="", description="Chinese summary of the review issue")
    suggested_action_zh: str = Field(default="", description="Suggested action in Chinese")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    needs_human_review: bool = Field(default=True, description="Whether this result needs human review")


class BatchAnalysisRequest(BaseModel):
    """Request body for batch review analysis."""

    reviews: list[ReviewInput] = Field(..., min_length=1, description="List of reviews to analyze")


class BatchAnalysisResponse(BaseModel):
    """Response body for batch review analysis."""

    results: list[ReviewAnalysis] = Field(default_factory=list, description="List of analyzed reviews")
    total: int = Field(default=0, description="Total number of reviews analyzed")
    needs_human_review_count: int = Field(default=0, description="Number of reviews needing human review")


# ── API schemas (for future Milestone 3) ──────────────────────────────────────

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
    """Response body for POST /api/v1/analyze."""

    review_id: str
    sentiment: str
    issue_category: str
    priority: str
    responsible_team: str
    summary_zh: str
    suggested_action_zh: str
    confidence: float
    needs_human_review: bool


class HealthResponse(BaseModel):
    """Response body for GET /api/v1/health."""

    status: str
    service: str
