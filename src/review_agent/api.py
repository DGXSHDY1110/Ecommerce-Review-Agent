"""FastAPI application for the ecommerce review agent service.

Milestone 1: health check endpoint only.
Full analysis endpoints will be added in Milestone 3.
"""

from fastapi import FastAPI

from .schemas import HealthResponse

app = FastAPI(
    title="Ecommerce Review Agent",
    description="AI-powered cross-border e-commerce review monitoring and classification service",
    version="0.1.0",
)


@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Return service health status."""
    return HealthResponse(status="ok", service="ecommerce-review-agent")
