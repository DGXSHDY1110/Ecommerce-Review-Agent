"""Tests for report generation from analyzed review results."""

import pytest

from src.review_agent.report import generate_daily_report, generate_error_log_entry
from src.review_agent.schemas import ReviewAnalysis


def make_analysis(
    review_id="r001",
    sentiment="negative",
    issue_category="product_quality",
    priority="high",
    responsible_team="product",
    confidence=0.9,
    needs_human_review=False,
) -> ReviewAnalysis:
    """Helper to create a ReviewAnalysis for testing."""
    return ReviewAnalysis(
        review_id=review_id,
        sentiment=sentiment,
        issue_category=issue_category,
        priority=priority,
        responsible_team=responsible_team,
        summary_zh="测试摘要。",
        suggested_action_zh="测试建议。",
        confidence=confidence,
        needs_human_review=needs_human_review,
    )


class TestGenerateDailyReport:
    """Tests for generate_daily_report."""

    def test_empty_results(self):
        """Empty results should return a minimal report."""
        report = generate_daily_report([])
        assert "每日评论分析报告" in report
        assert "暂无数据" in report

    def test_report_includes_total_count(self):
        """Report should include the total number of reviews."""
        results = [make_analysis("r001"), make_analysis("r002")]
        report = generate_daily_report(results)
        assert "总评论数" in report
        assert "| 2 |" in report  # total count in table

    def test_report_includes_negative_count(self):
        """Report should count negative sentiment reviews."""
        results = [
            make_analysis("r001", sentiment="negative"),
            make_analysis("r002", sentiment="positive"),
            make_analysis("r003", sentiment="negative"),
        ]
        report = generate_daily_report(results)
        assert "负面评论" in report

    def test_report_includes_human_review_count(self):
        """Report should count reviews needing human review."""
        results = [
            make_analysis("r001", needs_human_review=True),
            make_analysis("r002", needs_human_review=False),
            make_analysis("r003", needs_human_review=True),
        ]
        report = generate_daily_report(results)
        assert "需要人工复核" in report

    def test_report_is_markdown(self):
        """Report should be valid Markdown with headers."""
        results = [make_analysis("r001")]
        report = generate_daily_report(results)
        assert report.startswith("# ")
        assert "## " in report

    def test_report_with_custom_title(self):
        """Report should accept custom title."""
        results = [make_analysis("r001")]
        report = generate_daily_report(results, title="自定义报告")
        assert "自定义报告" in report

    def test_report_excludes_api_keys(self):
        """Report must not contain any API key patterns."""
        results = [make_analysis("r001")]
        report = generate_daily_report(results)
        assert "sk-" not in report.lower()
        assert "api_key" not in report.lower()

    def test_report_includes_category_distribution(self):
        """Report should include issue category distribution."""
        results = [
            make_analysis("r001", issue_category="battery"),
            make_analysis("r002", issue_category="battery"),
            make_analysis("r003", issue_category="logistics"),
        ]
        report = generate_daily_report(results)
        assert "问题类别分布" in report
        assert "battery" in report
        assert "logistics" in report

    def test_report_includes_team_distribution(self):
        """Report should include responsible team distribution."""
        results = [
            make_analysis("r001", responsible_team="product"),
            make_analysis("r002", responsible_team="operations"),
        ]
        report = generate_daily_report(results)
        assert "责任团队分布" in report
        assert "product" in report
        assert "operations" in report

    def test_report_negative_section(self):
        """Report should have a negative reviews section."""
        results = [
            make_analysis("r001", sentiment="negative"),
            make_analysis("r002", sentiment="positive"),
        ]
        report = generate_daily_report(results)
        assert "重点负面评论" in report


class TestGenerateErrorLogEntry:
    """Tests for generate_error_log_entry."""

    def test_basic_entry(self):
        """Should produce valid JSON with review_id and error."""
        entry = generate_error_log_entry("r001", "JSON parse failed")
        import json
        parsed = json.loads(entry)
        assert parsed["review_id"] == "r001"
        assert "JSON parse failed" in parsed["error"]

    def test_entry_with_raw_output(self):
        """Should include truncated raw output."""
        long_output = "x" * 1000
        entry = generate_error_log_entry("r001", "error", long_output)
        import json
        parsed = json.loads(entry)
        assert len(parsed["raw_output"]) <= 500
