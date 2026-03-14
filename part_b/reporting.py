from __future__ import annotations

from part_b.schemas import AnalysesDocument, InterviewMetaDocument, TopicAnalysis


def render_report_markdown(
    *,
    meta: InterviewMetaDocument,
    analyses: AnalysesDocument,
) -> str:
    lines = [
        "# Interview Review Report",
        "",
        "## Basic Information",
        "",
        f"- Title: {meta.title}",
        f"- Interview ID: {meta.interview_id}",
        f"- Target Position: {meta.target_position or 'Not identified'}",
        f"- Direction: {meta.direction or 'Not identified'}",
        f"- Source File: {meta.source_file_name}",
    ]
    if meta.duration_seconds is not None:
        lines.append(f"- Duration (seconds): {meta.duration_seconds}")

    if analyses.summary is not None:
        summary = analyses.summary
        lines.extend(
            [
                "",
                "## Overall Summary",
                "",
                summary.overall_summary,
                "",
                "### Average Scores",
                "",
                "| Dimension | Score |",
                "| --- | --- |",
            ]
        )
        for metric, score in summary.average_scores.items():
            lines.append(f"| {metric} | {score} |")
        lines.extend(
            [
                "",
                "### Strengths",
                "",
                *_bullet_block(summary.strengths),
                "",
                "### Weaknesses",
                "",
                *_bullet_block(summary.weaknesses),
                "",
                "### 7-Day Action Plan",
                "",
                *_bullet_block(summary.action_plan_7d),
            ]
        )
        if summary.confidence_notes:
            lines.extend(
                [
                    "",
                    "### Confidence Notes",
                    "",
                    *_bullet_block(summary.confidence_notes),
                ]
            )

    lines.extend(["", "## Detailed Analysis", ""])
    for analysis in analyses.analyses:
        lines.extend(_topic_block(analysis))
    return "\n".join(lines).strip() + "\n"


def _topic_block(analysis: TopicAnalysis) -> list[str]:
    lines = [
        f"### Question {analysis.topic_id}: {analysis.main_question}",
        "",
        f"- Type: {analysis.question_understanding.question_type}",
        f"- Skills: {', '.join(analysis.question_understanding.skill_tested) or 'Not extracted'}",
        f"- Weighted Score: {analysis.rubric.weighted_total()}",
        f"- Reasoning: {analysis.rubric.reasoning}",
        "",
        "#### Expected Points",
        "",
        *_bullet_block(analysis.question_understanding.expected_points),
        "",
        "#### Strengths",
        "",
        *_bullet_block(analysis.strengths),
        "",
        "#### Issues",
        "",
        *_bullet_block(analysis.weaknesses),
        "",
        "#### Evidence",
        "",
        *_bullet_block(analysis.evidence_quotes),
    ]
    if analysis.reference_answer is not None:
        lines.extend(
            [
                "",
                "#### Reference Answer",
                "",
                "Must-Hit Points:",
                *_bullet_block(analysis.reference_answer.must_hit_points),
                "",
                "Standard Answer:",
                analysis.reference_answer.reference_standard,
                "",
                "Personalized Answer:",
                analysis.reference_answer.reference_personalized,
            ]
        )
        if analysis.reference_answer.answer_framework:
            lines.extend(
                [
                    "",
                    "Answer Framework:",
                    *_bullet_block(analysis.reference_answer.answer_framework),
                ]
            )
        if analysis.reference_answer.sources:
            lines.extend(
                [
                    "",
                    "Sources:",
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


def _bullet_block(items: list[str]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {item}" for item in items]


def _source_line(title: str, url: str | None, source_type: str) -> str:
    if url:
        return f"{title} ({source_type}) - {url}"
    return f"{title} ({source_type})"
