from __future__ import annotations

from core.time_utils import format_ms_range
from part_b.schemas import AnalysesDocument, InterviewMetaDocument, TopicAnalysis


def render_report_markdown(
    *,
    meta: InterviewMetaDocument,
    analyses: AnalysesDocument,
) -> str:
    lines = [
        "# 面试复盘报告",
        "",
        "## 基本信息",
        "",
        f"- 标题：{meta.title}",
        f"- 面试 ID：{meta.interview_id}",
        f"- 目标岗位：{meta.target_position or '未识别'}",
        f"- 面试方向：{meta.direction or '未识别'}",
        f"- 来源文件：{meta.source_file_name}",
    ]
    if meta.duration_seconds is not None:
        lines.append(f"- 时长（秒）：{meta.duration_seconds}")

    if analyses.summary is not None:
        summary = analyses.summary
        lines.extend(
            [
                "",
                "## 总体结论",
                "",
                summary.overall_summary,
                "",
                "### 平均得分",
                "",
                "| 维度 | 分数 |",
                "| --- | --- |",
            ]
        )
        for metric, score in summary.average_scores.items():
            lines.append(f"| {metric} | {score} |")
        lines.extend(
            [
                "",
                "### 优势",
                "",
                *_bullet_block(summary.strengths),
                "",
                "### 待改进",
                "",
                *_bullet_block(summary.weaknesses),
                "",
                "### 7 天行动计划",
                "",
                *_bullet_block(summary.action_plan_7d),
            ]
        )
        if summary.confidence_notes:
            lines.extend(
                [
                    "",
                    "### 置信度说明",
                    "",
                    *_bullet_block(summary.confidence_notes),
                ]
            )

    lines.extend(["", "## 逐题复盘", ""])
    for analysis in analyses.analyses:
        lines.extend(_topic_block(analysis))
    return "\n".join(lines).strip() + "\n"


def _topic_block(analysis: TopicAnalysis) -> list[str]:
    lines = [
        f"### 题目 {analysis.topic_id}：{analysis.main_question}",
        "",
        f"- 题型：{analysis.question_understanding.question_type}",
        f"- 考察能力：{', '.join(analysis.question_understanding.skill_tested) or '未提取'}",
        f"- 加权总分：{analysis.rubric.weighted_total()}",
        f"- 评分依据：{analysis.rubric.reasoning}",
        "",
        "#### 评分拆解",
        "",
        "| 维度 | 分数 |",
        "| --- | --- |",
    ]
    for label, score in _score_breakdown_rows(analysis):
        lines.append(f"| {label} | {score} |")
    lines.extend(
        [
            "",
            "#### 必答点",
            "",
            *_bullet_block(analysis.question_understanding.expected_points),
            "",
            "#### 优势",
            "",
            *_bullet_block(analysis.strengths),
            "",
            "#### 问题",
            "",
            *_bullet_block(analysis.weaknesses),
            "",
            "#### 证据时间线",
            "",
            *_bullet_block(_evidence_lines(analysis)),
        ]
    )
    if analysis.reference_answer is not None:
        lines.extend(
            [
                "",
                "#### 参考答案",
                "",
                "必答点：",
                *_bullet_block(analysis.reference_answer.must_hit_points),
                "",
                "标准答案：",
                analysis.reference_answer.reference_standard,
                "",
                "个性化答案：",
                analysis.reference_answer.reference_personalized,
            ]
        )
        if analysis.reference_answer.answer_framework:
            lines.extend(
                [
                    "",
                    "答题框架：",
                    *_bullet_block(analysis.reference_answer.answer_framework),
                ]
            )
        if analysis.reference_answer.sources:
            lines.extend(
                [
                    "",
                    "参考来源：",
                    *_bullet_block(
                        [
                            _source_line(source.title, source.url, source.source_type)
                            for source in analysis.reference_answer.sources
                        ]
                    ),
                ]
            )
    lines.extend([""])
    return lines


def _score_breakdown_rows(analysis: TopicAnalysis) -> list[tuple[str, str]]:
    label_map = {
        "accuracy": "准确性",
        "completeness": "完整性",
        "depth": "深度",
        "structure": "结构",
        "position_fit": "岗位匹配",
        "followup_handling": "追问处理",
        "weighted_total": "综合加权",
    }
    return [
        (label_map.get(key, key), _format_score_value(value))
        for key, value in analysis.rubric.score_breakdown().items()
    ]


def _format_score_value(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _evidence_lines(analysis: TopicAnalysis) -> list[str]:
    if analysis.evidence_items:
        return [
            f"[{format_ms_range(item.start_ms, item.end_ms)}] {item.text}"
            for item in analysis.evidence_items
            if item.text.strip()
        ]
    return analysis.evidence_quotes


def _bullet_block(items: list[str]) -> list[str]:
    if not items:
        return ["- 暂无"]
    return [f"- {item}" for item in items]


def _source_line(title: str, url: str | None, source_type: str) -> str:
    if url:
        return f"{title} ({source_type}) - {url}"
    return f"{title} ({source_type})"
