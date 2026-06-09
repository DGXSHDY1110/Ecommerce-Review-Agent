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
    summary_zh="测试摘要。",
    suggested_action_zh="测试建议。",
) -> ReviewAnalysis:
    """Helper to create a ReviewAnalysis for testing."""
    return ReviewAnalysis(
        review_id=review_id,
        sentiment=sentiment,
        issue_category=issue_category,
        priority=priority,
        responsible_team=responsible_team,
        summary_zh=summary_zh,
        suggested_action_zh=suggested_action_zh,
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
        assert "负面评论详情" in report

    def test_report_includes_human_review_section(self):
        """Report should have a dedicated Human Review Required section."""
        results = [
            make_analysis("r001", needs_human_review=True,
                         confidence=0.3, issue_category="other",
                         summary_zh="", suggested_action_zh=""),
            make_analysis("r002", needs_human_review=False),
        ]
        report = generate_daily_report(results)
        assert "需要人工复核" in report

    def test_report_includes_human_review_rules(self):
        """Report should explain when human review is triggered."""
        results = [make_analysis("r001")]
        report = generate_daily_report(results)
        assert "人工复核规则说明" in report or "Human Review Rules" in report
        # Check for key rule descriptions
        assert "低置信度" in report or "Low Confidence" in report

    def test_report_includes_confidence_stats(self):
        """Report should include average/min/max confidence."""
        results = [
            make_analysis("r001", confidence=0.5),
            make_analysis("r002", confidence=0.9),
            make_analysis("r003", confidence=0.7),
        ]
        report = generate_daily_report(results)
        assert "置信度" in report or "Confidence" in report

    def test_report_includes_priority_breakdown(self):
        """Report should include high/medium/low priority counts."""
        results = [
            make_analysis("r001", priority="high"),
            make_analysis("r002", priority="medium"),
            make_analysis("r003", priority="low"),
        ]
        report = generate_daily_report(results)
        assert "高优先级" in report
        assert "中优先级" in report
        assert "低优先级" in report

    def test_report_includes_error_log_reference(self):
        """Report should reference error_cases.jsonl."""
        results = [make_analysis("r001")]
        report = generate_daily_report(results)
        assert "error_cases.jsonl" in report or "error_cases" in report

    def test_report_with_all_needs_review(self):
        """Report should handle case where all reviews need human review."""
        results = [
            make_analysis("r001", needs_human_review=True, confidence=0.3),
            make_analysis("r002", needs_human_review=True, confidence=0.4),
        ]
        report = generate_daily_report(results)
        # Should not crash and should show the count
        assert "需要人工复核" in report


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

    def test_entry_is_single_line(self):
        """Error log entry should be a single line (JSONL format)."""
        entry = generate_error_log_entry("r001", "error")
        assert "\n" not in entry
