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
from src.review_agent.utils import log_error_case, ensure_output_dir


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


def count_error_log_entries() -> int:
    """Count the number of entries in the error log."""
    from src.review_agent.utils import ERROR_LOG_PATH
    try:
        if not ERROR_LOG_PATH.exists():
            return 0
        with open(ERROR_LOG_PATH, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


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
        log_error_case(
            review_id="batch",
            error_type="BATCH_FAILURE",
            error_message=str(e)[:500],
            fallback_used=True,
            needs_human_review=True,
        )
        sys.exit(1)

    # Save results
    print(f"💾 Saving JSON results to: {output_json}")
    save_json(output_json, response)

    # Generate and save report
    print(f"📝 Generating report: {output_report}")
    rating_map = {r.review_id: r.rating for r in reviews}
    report_md = generate_daily_report(response.results, rating_map=rating_map)
    save_report(output_report, report_md)

    # ── Final summary ─────────────────────────────────────────────────
    print()
    print("=" * 50)
    print("✅ Batch analysis complete!")
    print(f"   Total reviews:         {response.total}")
    print(f"   Needs human review:    {response.needs_human_review_count}")
    print(f"   JSON output:           {output_json}")
    print(f"   Report:                {output_report}")

    # ── Human review warning ──────────────────────────────────────────
    if response.needs_human_review_count > 0:
        print()
        print("⚠️ ════════════════════════════════════════════════════")
        print(f"   ⚠️  {response.needs_human_review_count} 条评论需要人工复核！")
        print("   ════════════════════════════════════════════════════")
        print()
        human_review_items = [
            r for r in response.results if r.needs_human_review
        ]
        print("   需人工复核的评论：")
        print(f"   {'ID':<8} {'评分':<5} {'情绪':<10} {'类别':<20} {'置信度':<7}")
        print(f"   {'─'*8} {'─'*5} {'─'*10} {'─'*20} {'─'*7}")
        for r in human_review_items[:20]:  # Show at most 20
            original_rating = rating_map.get(r.review_id, "?")
            print(
                f"   {r.review_id:<8} {str(original_rating):<5} "
                f"{r.sentiment:<10} {r.issue_category:<20} {r.confidence:<7.2f}"
            )
        if len(human_review_items) > 20:
            print(f"   ... 还有 {len(human_review_items) - 20} 条未显示")
        print()
        print("   请查看以下文件了解详情：")
        print(f"   - 报告: {output_report}")
        print(f"   - 结果: {output_json}")

        # Check error log
        error_count = count_error_log_entries()
        error_log_path = PROJECT_ROOT / "outputs" / "results" / "error_cases.jsonl"
        if error_count > 0:
            print(f"   - 错误日志: {error_log_path} ({error_count} 条记录)")
        print("   ════════════════════════════════════════════════════")
    else:
        print()
        print("   ✅ 所有评论均无需人工复核。")

    print()

    # ── Error log summary ─────────────────────────────────────────────
    error_count = count_error_log_entries()
    if error_count > 0:
        print(f"📋 错误案例日志: outputs/results/error_cases.jsonl ({error_count} 条)")
        print("   使用以下命令查看:")
        print("   head -n 5 outputs/results/error_cases.jsonl")
    else:
        print("📋 无错误案例记录。")

    print("=" * 50)


if __name__ == "__main__":
    main()
