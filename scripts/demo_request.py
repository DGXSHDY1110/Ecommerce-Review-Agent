"""Demo request script for verifying the FastAPI service.

Sends a test review to the local FastAPI server and prints the formatted
JSON response.  Supports both the health-check and single-analysis endpoints.

Usage:
    # Default: analyze a single review
    python scripts/demo_request.py

    # Custom URL
    python scripts/demo_request.py --url http://127.0.0.1:8000/api/v1/analyze

    # Health check only
    python scripts/demo_request.py --health
"""

import argparse
import json
import sys

import requests

DEFAULT_ANALYZE_URL = "http://127.0.0.1:8000/api/v1/analyze"
DEFAULT_HEALTH_URL = "http://127.0.0.1:8000/api/v1/health"

# ── Sample test review ─────────────────────────────────────────────────────────

SAMPLE_REVIEW = {
    "review_id": "demo001",
    "platform": "Amazon",
    "product_name": "Wireless Security Camera",
    "rating": 2,
    "review_text": "Battery drains too fast and the night vision is blurry.",
    "country": "US",
    "created_at": "2026-06-01",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def print_result(label: str, data: dict) -> None:
    """Pretty-print a JSON response with a header."""
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def check_health(url: str) -> bool:
    """Call GET /api/v1/health.  Returns True on success."""
    print(f"\n🔍 Checking health at: {url}")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        print_result("Health Check Response", resp.json())
        return True
    except requests.ConnectionError:
        print(f"\n❌ ERROR: Cannot connect to {url}")
        print("   Is the server running?")
        print("   Start with:")
        print("   LLM_MOCK_MODE=true uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000")
        return False
    except requests.HTTPError as exc:
        print(f"\n❌ HTTP Error: {exc}")
        return False
    except Exception as exc:
        print(f"\n❌ Unexpected error: {exc}")
        return False


def analyze_review(url: str) -> bool:
    """POST a sample review to the analyze endpoint.  Returns True on success."""
    print(f"\n📤 Sending review to: {url}")
    print(f"   Review ID: {SAMPLE_REVIEW['review_id']}")
    print(f"   Product:   {SAMPLE_REVIEW['product_name']}")
    print(f"   Rating:    {SAMPLE_REVIEW['rating']}")
    print(f"   Text:      {SAMPLE_REVIEW['review_text']}")

    try:
        resp = requests.post(
            url,
            json=SAMPLE_REVIEW,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        print_result("Analysis Result", resp.json())

        # Quick validation of response fields
        data = resp.json()
        required_fields = ["review_id", "sentiment", "issue_category",
                          "priority", "needs_human_review"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            print(f"\n⚠️  Warning: response missing fields: {missing}")
        else:
            print(f"\n✅ All required fields present: {', '.join(required_fields)}")
        return True

    except requests.ConnectionError:
        print(f"\n❌ ERROR: Cannot connect to {url}")
        print("   Is the server running?")
        print("   Start with:")
        print("   LLM_MOCK_MODE=true uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000")
        return False
    except requests.HTTPError as exc:
        print(f"\n❌ HTTP Error {exc.response.status_code}: {exc.response.text[:500]}")
        return False
    except json.JSONDecodeError:
        print(f"\n❌ ERROR: Response was not valid JSON")
        return False
    except Exception as exc:
        print(f"\n❌ Unexpected error: {exc}")
        return False


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo script for ecommerce-review-agent FastAPI service"
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_ANALYZE_URL,
        help=f"URL for the analyze endpoint (default: {DEFAULT_ANALYZE_URL})",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Only run the health check (skips analyze)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Ecommerce Review Agent — Demo Request Script")
    print("=" * 60)

    # Always run health check first
    health_ok = check_health(DEFAULT_HEALTH_URL)

    if not health_ok:
        sys.exit(1)

    if args.health:
        print("\n✅ Health check passed.  (--health mode: skipping analyze)")
        sys.exit(0)

    # Run analyze
    analyze_ok = analyze_review(args.url)

    if analyze_ok:
        print("\n✅ Demo completed successfully!")
    else:
        print("\n❌ Demo failed.  See errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
