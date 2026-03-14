from __future__ import annotations

from collections import Counter

from part_b.llm_utils import safe_invoke_json_model
from part_b.prompts.phase4 import INTERVIEW_SUMMARY_SYSTEM_PROMPT, build_interview_summary_prompt
from part_b.schemas import InterviewMetaDocument, InterviewSummary, ResumeProfileDocument, TopicAnalysis


ACTION_MAP = {
    "Answers lack sufficient detail": "Practice 2 high-frequency questions daily using the 'conclusion -> details -> result' structure until you can deliver a complete answer within 90 seconds.",
    "Missing principles, trade-offs, or quantified details": "For each project point, add 1 principle explanation, 1 trade-off description, and 1 result metric.",
    "Expression structure could be clearer": "Use the STAR or 'context-approach-result' template consistently when restating answers.",
    "Insufficient alignment with target position": "End each answer with a statement like 'This demonstrates my ability to excel in the target position because...'.",
    "Insufficient depth in follow-up questions": "Practice 3 rounds of consecutive follow-ups on the same question, focusing on principles, edge cases, and exceptions.",
    "Answers are too short, lacking evidence": "Prepare at least 1 case study, 1 number, and 1 result for each question.",
}


def generate_interview_summary(
    analyses: list[TopicAnalysis],
    *,
    meta: InterviewMetaDocument | None = None,
    resume: ResumeProfileDocument | None = None,
) -> InterviewSummary:
    fallback = _heuristic_summary(analyses, meta=meta)
    llm_result = safe_invoke_json_model(
        InterviewSummary,
        system_prompt=INTERVIEW_SUMMARY_SYSTEM_PROMPT,
        user_prompt=build_interview_summary_prompt(
            meta=meta.model_dump(mode="json") if meta else {},
            analyses=[analysis.model_dump(mode="json") for analysis in analyses],
        ),
        temperature=0.6,
        max_tokens=4096,
    )
    if llm_result is None:
        return fallback
    return _merge_summary(fallback, llm_result, meta=meta, resume=resume)


def _heuristic_summary(
    analyses: list[TopicAnalysis],
    *,
    meta: InterviewMetaDocument | None = None,
) -> InterviewSummary:
    average_scores = _average_scores(analyses)
    strengths = _top_items([item for analysis in analyses for item in analysis.strengths], limit=4)
    weaknesses = _top_items([item for analysis in analyses for item in analysis.weaknesses], limit=4)
    overall = average_scores.get("weighted_total", 0.0)
    target_position = meta.target_position if meta else None

    if overall >= 8:
        tone = "Performance is close to a strong pass"
    elif overall >= 7:
        tone = "Performance reaches a solid pass range"
    elif overall >= 6:
        tone = "Performance shows basic pass potential but lacks stability"
    else:
        tone = "Performance still has a noticeable gap from a stable pass"

    role_text = f"For the {target_position} position, " if target_position else ""
    overall_summary = (
        f"{role_text}{tone}. "
        f"Key strengths include: {_join_brief(strengths) or 'No significant strengths identified'}; "
        f"Priority areas for improvement: {_join_brief(weaknesses) or 'No significant weaknesses identified'}."
    )
    confidence_notes = _confidence_notes(analyses, overall)
    action_plan = _action_plan(weaknesses)

    return InterviewSummary(
        overall_summary=overall_summary,
        strengths=strengths,
        weaknesses=weaknesses,
        confidence_notes=confidence_notes,
        action_plan_7d=action_plan,
        average_scores=average_scores,
    )


def _merge_summary(
    fallback: InterviewSummary,
    llm_result: InterviewSummary,
    *,
    meta: InterviewMetaDocument | None,
    resume: ResumeProfileDocument | None,
) -> InterviewSummary:
    merged = llm_result.model_copy(deep=True)
    if not merged.overall_summary:
        merged.overall_summary = fallback.overall_summary
    if not merged.strengths:
        merged.strengths = fallback.strengths
    if not merged.weaknesses:
        merged.weaknesses = fallback.weaknesses
    if not merged.confidence_notes:
        merged.confidence_notes = fallback.confidence_notes
    if not merged.action_plan_7d:
        merged.action_plan_7d = fallback.action_plan_7d
    if not merged.average_scores:
        merged.average_scores = fallback.average_scores
    return merged


def _average_scores(analyses: list[TopicAnalysis]) -> dict[str, float]:
    if not analyses:
        return {}
    metrics = ("accuracy", "completeness", "depth", "structure", "position_fit", "followup_handling")
    averages: dict[str, float] = {}
    for metric in metrics:
        values = [
            getattr(analysis.rubric, metric)
            for analysis in analyses
            if getattr(analysis.rubric, metric) is not None
        ]
        if values:
            averages[metric] = round(sum(values) / len(values), 1)
    averages["weighted_total"] = round(
        sum(analysis.rubric.weighted_total() for analysis in analyses) / len(analyses),
        1,
    )
    return averages


def _top_items(items: list[str], *, limit: int) -> list[str]:
    counter = Counter(item.strip() for item in items if item.strip())
    return [item for item, _ in counter.most_common(limit)]


def _confidence_notes(analyses: list[TopicAnalysis], overall: float) -> list[str]:
    notes: list[str] = []
    if len(analyses) < 3:
        notes.append("Limited sample size; conclusions have low stability.")
    if overall < 7:
        notes.append("Current results are better suited as directional guidance rather than a final assessment.")
    if any(len(analysis.evidence_quotes) == 0 for analysis in analyses):
        notes.append("Some questions lack sufficient evidence; consider recording more complete samples.")
    return notes or ["Conclusions are based on collected questions and can be refined with more samples."]


def _action_plan(weaknesses: list[str]) -> list[str]:
    plans = [ACTION_MAP[item] for item in weaknesses if item in ACTION_MAP]
    if not plans:
        plans = [
            "Review high-frequency questions from this session and prepare 'conclusion-details-result' templates for each.",
            "Prepare 5 project highlights and 5 deep-dive follow-up answers aligned with your target position.",
        ]
    return plans[:4]


def _join_brief(items: list[str]) -> str:
    return ", ".join(items[:3])
