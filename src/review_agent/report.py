"""Report generation from analyzed review results.

Generates Chinese Markdown reports with summary statistics, category
distributions, responsible team distributions, and human-review listings.
"""

from collections import Counter
from typing import Optional

from .schemas import ReviewAnalysis


def generate_daily_report(
    results: list[ReviewAnalysis],
    title: Optional[str] = None,
    rating_map: Optional[dict[str, int]] = None,
) -> str:
    """Generate a Chinese Markdown daily report from a list of analysis results.

    The report includes:
    - Overview (total, sentiment breakdown, priority counts, average confidence)
    - Category distribution
    - Responsible team distribution
    - High-priority review details
    - Human review required list
    - Explanation of when human review is triggered

    Args:
        results: List of analyzed review results.
        title:   Optional report title. Defaults to "每日评论分析报告".

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

    # ── Category & team distribution ─────────────────────────────────────
    issue_counter: Counter[str] = Counter()
    team_counter: Counter[str] = Counter()
    for r in results:
        issue_counter[r.issue_category] += 1
        team_counter[r.responsible_team] += 1

    # ── Confidence stats ──────────────────────────────────────────────────
    confidences = [r.confidence for r in results]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    min_confidence = min(confidences) if confidences else 0.0
    max_confidence = max(confidences) if confidences else 0.0

    # ── Segmented results ─────────────────────────────────────────────────
    negative_reviews = [r for r in results if r.sentiment == "negative"]
    negative_reviews.sort(key=lambda r: r.confidence, reverse=True)

    human_review_items = [r for r in results if r.needs_human_review]
    human_review_items.sort(key=lambda r: r.confidence)

    high_priority_items = [r for r in results if r.priority == "high"]
    high_priority_items.sort(key=lambda r: r.confidence, reverse=True)

    # ── Build Markdown ────────────────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"# {report_title}")
    lines.append("")
    lines.append(f"> 生成时间：自动生成 | 总评论数：{total}")
    lines.append("")

    # ── Section 1: Overview ──────────────────────────────────────────────
    lines.append("## 📊 总览 Summary")
    lines.append("")
    lines.append("| 指标 Metric | 数量 Count | 占比 % |")
    lines.append("|-------------|-----------|--------|")
    lines.append(f"| 总评论数 Total Reviews | {total} | 100.0% |")
    lines.append(f"| 正面评论 Positive | {positive_count} | {positive_count/total*100:.1f}% |")
    lines.append(f"| 中性评论 Neutral | {neutral_count} | {neutral_count/total*100:.1f}% |")
    lines.append(f"| 负面评论 Negative | {negative_count} | {negative_count/total*100:.1f}% |")
    lines.append(f"| **需要人工复核 Human Review Required** | **{human_review_count}** | **{human_review_count/total*100:.1f}%** |")
    lines.append(f"| 高优先级 High Priority | {high_priority_count} | {high_priority_count/total*100:.1f}% |")
    lines.append(f"| 中优先级 Medium Priority | {medium_priority_count} | {medium_priority_count/total*100:.1f}% |")
    lines.append(f"| 低优先级 Low Priority | {low_priority_count} | {low_priority_count/total*100:.1f}% |")
    lines.append("")
    lines.append(f"**置信度 Confidence**: 平均 Avg={avg_confidence:.2f}, 最低 Min={min_confidence:.2f}, 最高 Max={max_confidence:.2f}")
    lines.append("")

    # ── Section 2: Category Distribution ─────────────────────────────────
    lines.append("## 📂 问题类别分布 Category Distribution")
    lines.append("")
    lines.append("| 类别 Category | 数量 Count | 占比 % |")
    lines.append("|--------------|-----------|--------|")
    for category, count in issue_counter.most_common():
        pct = count / total * 100
        lines.append(f"| {category} | {count} | {pct:.1f}% |")
    lines.append("")

    # ── Section 3: Responsible Team Distribution ────────────────────────
    lines.append("## 👥 责任团队分布 Responsible Team Distribution")
    lines.append("")
    lines.append("| 团队 Team | 数量 Count | 占比 % |")
    lines.append("|----------|-----------|--------|")
    for team, count in team_counter.most_common():
        pct = count / total * 100
        lines.append(f"| {team} | {count} | {pct:.1f}% |")
    lines.append("")

    # ── Section 4: High Priority Reviews ─────────────────────────────────
    lines.append("## 🔴 高优先级评论 High Priority Reviews")
    lines.append("")
    if high_priority_items:
        lines.append(f"共 {len(high_priority_items)} 条高优先级评论：")
        lines.append("")
        for i, r in enumerate(high_priority_items, 1):
            lines.append(f"### {i}. [{r.review_id}] {r.issue_category} (置信度: {r.confidence:.2f})")
            lines.append("")
            lines.append(f"- **情绪 Sentiment**: {r.sentiment}")
            lines.append(f"- **优先级 Priority**: {r.priority}")
            lines.append(f"- **责任团队 Team**: {r.responsible_team}")
            lines.append(f"- **中文摘要**: {r.summary_zh}")
            lines.append(f"- **建议动作**: {r.suggested_action_zh}")
            lines.append(f"- **需人工复核**: {'⚠️ 是 Yes' if r.needs_human_review else '否 No'}")
            lines.append("")
    else:
        lines.append("本批次无高优先级评论。")
        lines.append("")

    # ── Section 5: Human Review Required ─────────────────────────────────
    lines.append("## ⚠️ 需要人工复核 Human Review Required")
    lines.append("")
    if human_review_items:
        lines.append(f"共 **{len(human_review_items)}** 条评论需要人工复核：")
        lines.append("")
        lines.append("| Review ID | 评分 | 情绪 | 类别 | 优先级 | 置信度 | 原因 |")
        lines.append("|-----------|------|------|------|--------|--------|------|")
        for r in human_review_items:
            # Infer the likely reason for human review flag
            reasons: list[str] = []
            if r.confidence < 0.6:
                reasons.append("低置信度")
            if r.issue_category == "other":
                reasons.append("无法归类")
            if not (r.summary_zh or "").strip():
                reasons.append("摘要为空")
            if not (r.suggested_action_zh or "").strip():
                reasons.append("建议为空")
            reason_str = ", ".join(reasons) if reasons else "规则触发"
            rating_display = str(rating_map.get(r.review_id, "?")) if rating_map else "-"
            lines.append(
                f"| {r.review_id} | {rating_display} | {r.sentiment} "
                f"| {r.issue_category} | {r.priority} | {r.confidence:.2f} | {reason_str} |"
            )
        lines.append("")
    else:
        lines.append("本批次所有评论均无需人工复核。")
        lines.append("")

    # ── Section 6: Explanation of Human Review Rules ─────────────────────
    lines.append("## 📋 人工复核规则说明 Human Review Rules")
    lines.append("")
    lines.append("以下情况会自动标记为需要人工复核：")
    lines.append("")
    lines.append("| # | 规则 Rule | 说明 Description |")
    lines.append("|---|-----------|------------------|")
    lines.append("| 1 | **低置信度 Low Confidence** | 置信度 < 0.6，LLM 对分类结果不确定 |")
    lines.append("| 2 | **评分-情绪矛盾 Rating/Sentiment Contradiction** | 评分 ≤ 2 但情绪不是 negative，或评分 ≥ 4 但情绪是 negative |")
    lines.append("| 3 | **无法归类+低评分 Uncategorized + Low Rating** | 类别为 other 且评分 ≤ 2 |")
    lines.append("| 4 | **中文摘要缺失 Missing Summary** | summary_zh 或 suggested_action_zh 为空 |")
    lines.append("| 5 | **API 调用失败 API Failure** | LLM API 超时、网络错误、JSON 解析失败 → 使用安全兜底 |")
    lines.append("| 6 | **Schema 校验失败 Schema Validation Failed** | LLM 输出的 JSON 不符合 Pydantic Schema → 重试 → 兜底 |")
    lines.append("")
    lines.append("> 💡 **设计原则**: \"宁可多报，不可漏报\"。所有不确定的结果都会标记为需要人工复核，")
    lines.append("> 确保业务决策始终有 human-in-the-loop。")
    lines.append("")

    # ── Section 7: Negative Reviews Detail ────────────────────────────────
    lines.append("## 🔍 负面评论详情 Negative Reviews Detail")
    lines.append("")
    if negative_reviews:
        for i, r in enumerate(negative_reviews, 1):
            lines.append(f"### {i}. [{r.review_id}] {r.issue_category} (置信度: {r.confidence:.2f})")
            lines.append("")
            lines.append(f"- **情绪**: {r.sentiment}")
            lines.append(f"- **优先级**: {r.priority}")
            lines.append(f"- **责任团队**: {r.responsible_team}")
            lines.append(f"- **摘要**: {r.summary_zh}")
            lines.append(f"- **建议**: {r.suggested_action_zh}")
            lines.append(f"- **需人工复核**: {'⚠️ 是' if r.needs_human_review else '否'}")
            lines.append("")
    else:
        lines.append("本批次无负面评论。")
        lines.append("")

    # ── Footer ───────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("*本报告由 Ecommerce Review Agent (AI 应用工程 MVP) 自动生成。*")
    lines.append("")
    lines.append("*需要人工复核的评论已标记 ⚠️，请优先处理。*")
    lines.append("")
    lines.append("*失败案例详见 `outputs/results/error_cases.jsonl`。*")
    lines.append("")

    return "\n".join(lines)


def generate_error_log_entry(review_id: str, error_message: str, raw_output: str = "") -> str:
    """Generate a single JSONL error log entry.

    Args:
        review_id:     The review identifier.
        error_message: Description of the error.
        raw_output:    Optional raw LLM output that caused the error.

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
