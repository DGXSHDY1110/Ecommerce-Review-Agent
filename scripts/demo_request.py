"""Demo request script for verifying the FastAPI service.

Sends test review(s) to the local FastAPI server and prints the formatted
JSON response.  Supports health check, single analysis, and batch analysis.

Usage:
    # Single review analysis (default)
    python scripts/demo_request.py --mode single

    # Batch analysis
    python scripts/demo_request.py --mode batch

    # Health check only
    python scripts/demo_request.py --health

    # Custom URL
    python scripts/demo_request.py --mode single --url http://127.0.0.1:8000/api/v1/analyze

Note: This script only calls the local FastAPI service — it never calls
DeepSeek directly.  Whether the analysis uses real LLM or mock depends on
the FastAPI server's environment (USE_MOCK_LLM / DEEPSEEK_API_KEY).
"""

import argparse
import json
import sys

import requests

DEFAULT_ANALYZE_URL = "http://127.0.0.1:8000/api/v1/analyze"
DEFAULT_BATCH_URL = "http://127.0.0.1:8000/api/v1/analyze_batch"
DEFAULT_HEALTH_URL = "http://127.0.0.1:8000/api/v1/health"
DEFAULT_MODE_URL = "http://127.0.0.1:8000/api/v1/mode"

# ── Sample test data ───────────────────────────────────────────────────────────

SAMPLE_REVIEW = {
    "review_id": "demo001",
    "platform": "Amazon",
    "product_name": "Wireless Security Camera",
    "rating": 2,
    "review_text": "Battery drains too fast and the night vision is blurry.",
    "country": "US",
    "created_at": "2026-06-01",
}

SAMPLE_BATCH = {
    "reviews": [
        {
            "review_id": "demo001",
            "platform": "Amazon",
            "product_name": "Wireless Security Camera",
            "rating": 2,
            "review_text": "Battery drains too fast and the night vision is blurry.",
            "country": "US",
            "created_at": "2026-06-01",
        },
        {
            "review_id": "demo002",
            "platform": "Shopify",
            "product_name": "Yoga Mat",
            "rating": 4,
            "review_text": "Good mat, nice thickness. Delivery took longer than expected.",
            "country": "DE",
            "created_at": "2026-06-02",
        },
        {
            "review_id": "demo003",
            "platform": "Amazon",
            "product_name": "USB Cable",
            "rating": 3,
            "review_text": "It's okay I guess.",
            "country": "US",
            "created_at": "2026-06-03",
        },
    ]
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def print_result(label: str, data: dict) -> None:
    """Pretty-print a JSON response with a header."""
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # Highlight V2-M1 fields if present
    v2_fields = ["evidence", "llm_mode", "is_mock", "model", "processing_time_ms"]
    present = [f for f in v2_fields if f in data]
    if present:
        print(f"\n  📋 V2 Fields: {', '.join(present)}")


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
        print("   Is the server running? Start with:")
        print("   USE_MOCK_LLM=true uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000")
        return False
    except requests.HTTPError as exc:
        print(f"\n❌ HTTP Error: {exc}")
        return False
    except Exception as exc:
        print(f"\n❌ Unexpected error: {exc}")
        return False


def check_mode(url: str) -> bool:
    """Call GET /api/v1/mode. Returns True on success."""
    print(f"\n🔍 Checking mode at: {url}")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        print_result("Service Mode", data)

        mode = data.get("llm_mode", "unknown")
        is_mock = data.get("use_mock_llm", None)
        model = data.get("model", "?")
        key_ok = data.get("api_key_configured", False)

        print(f"\n  📋 Mode: {mode} | Mock: {is_mock} | Model: {model} | API Key: {'✅' if key_ok else '❌'}")
        if is_mock:
            print("  ⚠️  WARNING: Service is in MOCK mode — results are keyword-based, not real AI.")
        elif not key_ok:
            print("  ⚠️  WARNING: DEEPSEEK_API_KEY not configured — real LLM calls will fail.")
        return True
    except requests.ConnectionError:
        print(f"\n❌ Cannot connect to {url}. Is the server running?")
        return False
    except Exception as exc:
        print(f"\n❌ Error: {exc}")
        return False


def analyze_single(url: str) -> bool:
    """POST a single sample review to the analyze endpoint."""
    print(f"\n📤 Sending SINGLE review to: {url}")
    print(f"   Review ID: {SAMPLE_REVIEW['review_id']}")
    print(f"   Rating:    {SAMPLE_REVIEW['rating']}")
    print(f"   Text:      {SAMPLE_REVIEW['review_text']}")

    try:
        resp = requests.post(
            url,
            json=SAMPLE_REVIEW,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        print_result("Analysis Result", data)

        # Validate required fields
        required = ["review_id", "sentiment", "issue_category", "priority",
                     "needs_human_review", "evidence", "llm_mode"]
        missing = [f for f in required if f not in data]
        if missing:
            print(f"\n⚠️  Missing fields: {missing}")
            return False

        # Show mode
        mode = data.get("llm_mode", "unknown")
        model = data.get("model", "unknown")
        is_mock = data.get("is_mock", None)
        evidence_count = len(data.get("evidence", []))
        print(f"\n✅ Mode: {mode} | Model: {model} | is_mock: {is_mock} | evidence items: {evidence_count}")
        return True

    except requests.ConnectionError:
        print(f"\n❌ Cannot connect to {url}. Is the server running?")
        return False
    except requests.HTTPError as exc:
        print(f"\n❌ HTTP {exc.response.status_code}: {exc.response.text[:500]}")
        return False
    except json.JSONDecodeError:
        print(f"\n❌ Response was not valid JSON")
        return False
    except Exception as exc:
        print(f"\n❌ Unexpected error: {exc}")
        return False


def analyze_batch(url: str) -> bool:
    """POST a batch of sample reviews to the batch endpoint."""
    print(f"\n📤 Sending BATCH ({len(SAMPLE_BATCH['reviews'])} reviews) to: {url}")

    try:
        resp = requests.post(
            url,
            json=SAMPLE_BATCH,
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        # Print summary
        total = data.get("total", 0)
        real = data.get("real_count", "?")
        mock = data.get("mock_count", "?")
        errors = data.get("error_count", "?")
        human = data.get("needs_human_review_count", "?")

        print(f"\n  📊 Batch Summary:")
        print(f"     Total: {total}  |  Real: {real}  |  Mock: {mock}")
        print(f"     Errors: {errors}  |  Needs Human Review: {human}")

        # Print each result's key fields
        print(f"\n  {'ID':<10} {'Sentiment':<10} {'Category':<22} {'Mode':<6} {'Evidence':<5}")
        print(f"  {'─'*10} {'─'*10} {'─'*22} {'─'*6} {'─'*5}")
        for r in data.get("results", []):
            evidence_count = len(r.get("evidence", []))
            print(
                f"  {r.get('review_id', '?'):<10} {r.get('sentiment', '?'):<10} "
                f"{r.get('issue_category', '?'):<22} {r.get('llm_mode', '?'):<6} "
                f"{evidence_count:<5}"
            )

        print_result("Full Batch Response", data)
        return True

    except requests.ConnectionError:
        print(f"\n❌ Cannot connect to {url}. Is the server running?")
        return False
    except requests.HTTPError as exc:
        print(f"\n❌ HTTP {exc.response.status_code}: {exc.response.text[:500]}")
        return False
    except json.JSONDecodeError:
        print(f"\n❌ Response was not valid JSON")
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
        "--mode",
        choices=["single", "batch", "status"],
        default="single",
        help="Demo mode: single (default), batch, or status (check service mode)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Override the default endpoint URL",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Only run the health check (skips analysis)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Ecommerce Review Agent — Demo Request Script")
    print(f"  Mode: {args.mode}")
    print("=" * 60)

    # Always run health check first
    health_ok = check_health(DEFAULT_HEALTH_URL)
    if not health_ok:
        sys.exit(1)

    if args.health:
        print("\n✅ Health check passed. (--health mode: skipping analysis)")
        sys.exit(0)

    # Run selected mode
    if args.mode == "status":
        ok = check_mode(args.url or DEFAULT_MODE_URL)
    elif args.mode == "batch":
        batch_url = args.url or DEFAULT_BATCH_URL
        ok = analyze_batch(batch_url)
    else:
        single_url = args.url or DEFAULT_ANALYZE_URL
        ok = analyze_single(single_url)

    if ok:
        print("\n✅ Demo completed successfully!")
    else:
        print("\n❌ Demo failed. See errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
