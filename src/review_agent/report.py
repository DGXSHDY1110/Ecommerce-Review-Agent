"""Report generation from analyzed review results.

Generates Chinese Markdown reports with summary statistics.
"""

from collections import Counter
from typing import Optional

from .schemas import ReviewAnalysis


def generate_daily_report(results: list[ReviewAnalysis], title: Optional[str] = None) -> str:
    """Generate a Chinese Markdown daily report from a list of analysis results.

    Args:
        results: List of analyzed review results.
        title: Optional report title. Defaults to "每日评论分析报告".

    Returns:
        Markdown-formatted report string.
    """
    if not results:
        return "# 每日评论分析报告\n\n暂无数据。\n"

    report_title = title or "每日评论分析报告"

    # ── Basic counts ──────────────────────────────────────────────────────
    total = len(results)
    negative_count = sum(1 for r in results if r.sentiment == "negative")
    positive_count = sum(1 for r in results if r.sentiment == "positive")
    neutral_count = sum(1 for r in results if r.sentiment == "neutral")
    human_review_count = sum(1 for r in results if r.needs_human_review)
    high_priority_count = sum(1 for r in results if r.priority == "high")
    medium_priority_count = sum(1 for r in results if r.priority == "medium")
    low_priority_count = sum(1 for r in results if r.priority == "low")

    # ── Category distribution ─────────────────────────────────────────────
    issue_counter: Counter[str] = Counter()
    team_counter: Counter[str] = Counter()
    for r in results:
        issue_counter[r.issue_category] += 1
        team_counter[r.responsible_team] += 1

    # ── Confidence stats ──────────────────────────────────────────────────
    confidences = [r.confidence for r in results]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    # ── Top negative reviews ──────────────────────────────────────────────
    negative_reviews = [r for r in results if r.sentiment == "negative"]
    negative_reviews.sort(key=lambda r: r.confidence, reverse=True)

    # ── Build Markdown ────────────────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"# {report_title}")
    lines.append("")

    # Summary section
    lines.append("## 📊 总览")
    lines.append("")
    lines.append("| 指标 | 数量 |")
    lines.append("|------|------|")
    lines.append(f"| 总评论数 | {total} |")
    lines.append(f"| 正面评论 | {positive_count} |")
    lines.append(f"| 中性评论 | {neutral_count} |")
    lines.append(f"| 负面评论 | {negative_count} |")
    lines.append(f"| 需要人工复核 | {human_review_count} |")
    lines.append(f"| 高优先级 | {high_priority_count} |")
    lines.append(f"| 中优先级 | {medium_priority_count} |")
    lines.append(f"| 低优先级 | {low_priority_count} |")
    lines.append(f"| 平均置信度 | {avg_confidence:.2f} |")
    lines.append("")

    # Issue category distribution
    lines.append("## 📂 问题类别分布")
    lines.append("")
    lines.append("| 类别 | 数量 | 占比 |")
    lines.append("|------|------|------|")
    for category, count in issue_counter.most_common():
        pct = count / total * 100
        lines.append(f"| {category} | {count} | {pct:.1f}% |")
    lines.append("")

    # Responsible team distribution
    lines.append("## 👥 责任团队分布")
    lines.append("")
    lines.append("| 团队 | 数量 | 占比 |")
    lines.append("|------|------|------|")
    for team, count in team_counter.most_common():
        pct = count / total * 100
        lines.append(f"| {team} | {count} | {pct:.1f}% |")
    lines.append("")

    # Top negative reviews
    lines.append("## 🔴 重点负面评论")
    lines.append("")
    if negative_reviews:
        for i, r in enumerate(negative_reviews[:10], 1):
            lines.append(f"### {i}. [{r.review_id}] {r.issue_category} (置信度: {r.confidence:.2f})")
            lines.append("")
            lines.append(f"- **情绪**: {r.sentiment}")
            lines.append(f"- **优先级**: {r.priority}")
            lines.append(f"- **责任团队**: {r.responsible_team}")
            lines.append(f"- **摘要**: {r.summary_zh}")
            lines.append(f"- **建议**: {r.suggested_action_zh}")
            lines.append(f"- **需人工复核**: {'是' if r.needs_human_review else '否'}")
            lines.append("")
    else:
        lines.append("无负面评论。")
        lines.append("")

    # Notes
    lines.append("---")
    lines.append(f"*报告由 Ecommerce Review Agent 自动生成。需要人工复核的评论请优先处理。*")
    lines.append("")

    return "\n".join(lines)


def generate_error_log_entry(review_id: str, error_message: str, raw_output: str = "") -> str:
    """Generate a single JSONL error log entry.

    Args:
        review_id: The review identifier.
        error_message: Description of the error.
        raw_output: Optional raw LLM output that caused the error.

    Returns:
        A single JSON line (without trailing newline).
    """
    import json

    return json.dumps(
        {
            "review_id": review_id,
            "error": error_message,
            "raw_output": raw_output[:500] if raw_output else "",
        },
        ensure_ascii=False,
    )
