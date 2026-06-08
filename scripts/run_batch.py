"""Batch review analysis script.

Reads review data from a CSV file, runs the classification workflow,
and writes results to JSON and a Markdown report.

Usage:
    python scripts/run_batch.py --mock
    python scripts/run_batch.py --input data/mock/sample_reviews.csv --mock
    python scripts/run_batch.py --input data/mock/sample_reviews.csv
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure the project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.review_agent.config import get_settings, Settings
from src.review_agent.llm_client import LLMClient
from src.review_agent.schemas import (
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    ReviewInput,
)
from src.review_agent.workflow import analyze_batch_request
from src.review_agent.report import generate_daily_report


def read_reviews_csv(csv_path: str) -> list[ReviewInput]:
    """Read reviews from a CSV file and return a list of ReviewInput objects.

    Expected CSV columns:
        review_id, platform, product_name, rating, review_text, country, created_at
    """
    reviews: list[ReviewInput] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            review = ReviewInput(
                review_id=row["review_id"].strip(),
                platform=row["platform"].strip(),
                product_name=row["product_name"].strip(),
                rating=int(row["rating"]),
                review_text=row["review_text"].strip(),
                country=row["country"].strip(),
                created_at=row["created_at"].strip(),
            )
            reviews.append(review)
    return reviews


def ensure_output_dirs(json_path: str, report_path: str) -> None:
    """Create output directories if they don't exist."""
    for path in (json_path, report_path):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)


def save_json(path: str, response: BatchAnalysisResponse) -> None:
    """Save BatchAnalysisResponse as JSON."""
    data = response.model_dump()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_report(path: str, markdown: str) -> None:
    """Save markdown report to file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run batch review analysis using DeepSeek LLM or mock mode."
    )
    parser.add_argument(
        "--input",
        default="data/mock/sample_reviews.csv",
        help="Path to input CSV file (default: data/mock/sample_reviews.csv)",
    )
    parser.add_argument(
        "--output-json",
        default="outputs/results/review_analysis.json",
        help="Path for JSON output (default: outputs/results/review_analysis.json)",
    )
    parser.add_argument(
        "--output-report",
        default="outputs/reports/daily_report.md",
        help="Path for Markdown report (default: outputs/reports/daily_report.md)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock mode without calling the real DeepSeek API",
    )
    args = parser.parse_args()

    # Resolve input path relative to project root
    input_path = os.path.join(PROJECT_ROOT, args.input)
    if not os.path.isfile(input_path):
        # Also try as-is and legacy path
        alt_path = os.path.join(PROJECT_ROOT, "data", "sample_reviews.csv")
        if os.path.isfile(alt_path):
            input_path = alt_path
        else:
            print(f"❌ Input file not found: {input_path}")
            print(f"   Also tried: {alt_path}")
            sys.exit(1)

    output_json = os.path.join(PROJECT_ROOT, args.output_json)
    output_report = os.path.join(PROJECT_ROOT, args.output_report)

    # Create output directories
    ensure_output_dirs(output_json, output_report)

    # Configure settings
    settings = get_settings()
    if args.mock:
        settings.llm_mock_mode = True
        print("🔧 Running in MOCK mode — no real API calls will be made.")
    else:
        if not settings.deepseek_api_key:
            print("⚠️  DEEPSEEK_API_KEY not set. Switching to mock mode automatically.")
            settings.llm_mock_mode = True
        else:
            print(f"🚀 Running with DeepSeek API: model={settings.deepseek_model}")

    # Read input
    print(f"📖 Reading reviews from: {input_path}")
    try:
        reviews = read_reviews_csv(input_path)
    except Exception as e:
        print(f"❌ Failed to read CSV: {e}")
        sys.exit(1)

    print(f"   Found {len(reviews)} reviews.")

    if not reviews:
        print("⚠️  No reviews to process. Exiting.")
        sys.exit(0)

    # Run analysis
    print("🔍 Analyzing reviews...")
    request = BatchAnalysisRequest(reviews=reviews)
    client = LLMClient(settings=settings)
    try:
        response = analyze_batch_request(request, client=client)
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        sys.exit(1)

    # Save results
    print(f"💾 Saving JSON results to: {output_json}")
    save_json(output_json, response)

    # Generate and save report
    print(f"📝 Generating report: {output_report}")
    report_md = generate_daily_report(response.results)
    save_report(output_report, report_md)

    # Summary
    print()
    print("=" * 50)
    print("✅ Batch analysis complete!")
    print(f"   Total reviews:         {response.total}")
    print(f"   Needs human review:    {response.needs_human_review_count}")
    print(f"   JSON output:           {output_json}")
    print(f"   Report:                {output_report}")
    print("=" * 50)


if __name__ == "__main__":
    main()
