"""Demo request script for verifying the FastAPI service.

Milestone 1: health check request only.
Full analysis demo will be added in Milestone 3.

Usage:
    python scripts/demo_request.py
"""

import httpx
import json


API_BASE = "http://127.0.0.1:8000"


def check_health():
    """Call GET /api/v1/health and print the response."""
    url = f"{API_BASE}/api/v1/health"
    try:
        response = httpx.get(url)
        response.raise_for_status()
        data = response.json()
        print("Health check response:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data
    except httpx.ConnectError:
        print(f"ERROR: Cannot connect to {API_BASE}. Is the server running?")
        print(f"Start with: uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None


def analyze_review():
    """Placeholder for POST /api/v1/analyze (will be implemented in Milestone 3)."""
    print("\n[Placeholder] POST /api/v1/analyze — not yet implemented.")


if __name__ == "__main__":
    print("=" * 60)
    print("Ecommerce Review Agent — Demo Request Script")
    print("=" * 60)

    health_result = check_health()

    if health_result and health_result.get("status") == "ok":
        print("\n✅ Health check passed. Service is running.")
        analyze_review()
    else:
        print("\n❌ Health check failed. See error above.")
