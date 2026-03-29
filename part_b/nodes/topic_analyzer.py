from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from config import get_settings
from part_b.llm_utils import safe_invoke_json_model
from part_b.prompts.phase4 import (
    REFERENCE_ANSWER_SYSTEM_PROMPT,
    TOPIC_EVALUATION_SYSTEM_PROMPT,
    build_reference_answer_prompt,
    build_topic_evaluation_prompt,
)
from part_b.reference_adapter import ReferenceProvider, get_default_reference_provider
from part_b.schemas import (
    AnalysesDocument,
    EvidenceSnippet,
    InterviewMetaDocument,
    QaPairsDocument,
    QuestionUnderstanding,
    ReferenceAnswer,
    ResumeProfileDocument,
    RubricScore,
    TopicAnalysis,
    TopicGroup,
)


QUESTION_TYPE_LABELS = {
    "technical": "technical",
    "project": "project",
    "behavioral": "behavioral",
    "hr": "hr",
    "other": "general",
}

SKILL_RULES: list[tuple[str, tuple[str, ...], list[str]]] = [
    (
        "redis/cache",
        ("redis", "\u7f13\u5b58", "cache", "\u5931\u6548", "\u70ed\u70b9"),
        ["usage scenario", "invalidation or consistency strategy", "concurrency risk and fallback"],
    ),
    (
        "database",
        ("mysql", "sql", "\u4e8b\u52a1", "\u7d22\u5f15", "\u6570\u636e\u5e93"),
        ["data model or query path", "performance optimization", "transaction or consistency handling"],
    ),
    (
        "agent/orchestration",
        ("agent", "\u591aagent", "langgraph", "langchain", "\u56fe\u72b6\u6001\u673a"),
        ["task decomposition", "state flow or orchestration", "why this pattern fits the scenario"],
    ),
    (
        "rag/retrieval",
        ("rag", "\u53ec\u56de", "\u5411\u91cf", "\u77e5\u8bc6\u5e93", "\u51c6\u786e\u7387"),
        ["baseline quality or problem", "optimization levers", "validation method or measurable result"],
    ),
    (
        "project ownership",
        ("\u9879\u76ee", "\u8d1f\u8d23", "\u843d\u5730", "\u63a8\u8fdb", "\u534f\u4f5c"),
        ["project background", "personal ownership", "key decision and outcome"],
    ),
    (
        "behavioral",
        ("\u4e3a\u4ec0\u4e48", "\u51b2\u7a81", "\u6c9f\u901a", "\u6311\u6218", "\u4f18\u70b9", "\u7f3a\u70b9", "\u89c4\u5212"),
        ["context", "action", "result and reflection"],
    ),
]

LOW_DETAIL_HINTS = ("kind of", "maybe", "\u5c31\u662f", "\u8fd9\u4e2a", "\u90a3\u4e2a")
STRUCTURE_HINTS = ("first", "then", "finally", "\u9996\u5148", "\u7136\u540e", "\u6700\u540e")
DEPTH_HINTS = ("because", "therefore", "\u53d6\u820d", "\u539f\u7406", "\u98ce\u9669", "\u4e00\u81f4\u6027", "\u8fb9\u754c")
EXAMPLE_HINTS = ("for example", "\u6bd4\u5982", "\u4f8b\u5982", "\u9879\u76ee\u91cc", "\u6307\u6807", "qps", "%", "\u6beb\u79d2")


class TopicEvaluationDraft(BaseModel):
    question_understanding: QuestionUnderstanding
    rubric: RubricScore
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)


def analyze_topic(
    topic: TopicGroup,
    *,
    meta: InterviewMetaDocument | None = None,
    resume: ResumeProfileDocument | None = None,
    reference_provider: ReferenceProvider | None = None,
) -> TopicAnalysis:
    provider = reference_provider or get_default_reference_provider()
    settings = get_settings()
    evidence_items = _evidence_items(topic)

    fallback_understanding = _heuristic_question_understanding(topic)
    fallback_reference = _heuristic_reference_answer(
        topic,
        question_understanding=fallback_understanding,
        resume=resume,
        reference_provider=provider,
    )

    llm_reference = safe_invoke_json_model(
        ReferenceAnswer,
        system_prompt=REFERENCE_ANSWER_SYSTEM_PROMPT,
        user_prompt=build_reference_answer_prompt(
            meta={},
            resume=resume.model_dump(mode="json") if resume else None,
            topic=topic.model_dump(mode="json"),
            reference_context={
                "bullet_points": provider.build_context(topic=topic, meta=meta, resume=resume).bullet_points,
                "fallback_reference": fallback_reference.model_dump(mode="json"),
            },
        ),
        temperature=0.2,
        max_tokens=3072,
        model_name=settings.llm_structured_model,
        json_mode=True,
    )
    reference_answer = _merge_reference_answer(fallback_reference, llm_reference)

    fallback_evaluation = _heuristic_topic_evaluation(
        topic,
        resume=resume,
        reference_answer=reference_answer,
        question_understanding=fallback_understanding,
        evidence_items=evidence_items,
    )
    llm_evaluation = safe_invoke_json_model(
        TopicEvaluationDraft,
        system_prompt=TOPIC_EVALUATION_SYSTEM_PROMPT,
        user_prompt=build_topic_evaluation_prompt(
            meta={},
            resume=resume.model_dump(mode="json") if resume else None,
            topic=topic.model_dump(mode="json"),
            reference_answer=reference_answer.model_dump(mode="json"),
        ),
        temperature=0.2,
        max_tokens=3072,
        model_name=settings.llm_structured_model,
        json_mode=True,
    )
    evaluation = _merge_topic_evaluation(fallback_evaluation, llm_evaluation)

    return TopicAnalysis(
        topic_id=topic.topic_id,
        main_question=topic.question_text or topic.main_question,
        question_understanding=evaluation.question_understanding,
        rubric=evaluation.rubric,
        strengths=evaluation.strengths,
        weaknesses=evaluation.weaknesses,
        evidence_quotes=evaluation.evidence_quotes,
        evidence_items=evidence_items,
        reference_answer=reference_answer,
    )


def analyze_topics(
    document: QaPairsDocument,
    *,
    meta: InterviewMetaDocument | None = None,
    resume: ResumeProfileDocument | None = None,
    reference_provider: ReferenceProvider | None = None,
) -> AnalysesDocument:
    analyses = [
        analyze_topic(topic, meta=meta, resume=resume, reference_provider=reference_provider)
        for topic in document.topics
    ]
    return AnalysesDocument(interview_id=document.interview_id, analyses=analyses)


def _heuristic_question_understanding(topic: TopicGroup) -> QuestionUnderstanding:
    skills = _skill_tested(topic)
    return QuestionUnderstanding(
        question_type=QUESTION_TYPE_LABELS.get(topic.topic_type, "general"),
        skill_tested=skills,
        expected_points=_expected_points(topic, skills),
    )


def _heuristic_reference_answer(
    topic: TopicGroup,
    *,
    question_understanding: QuestionUnderstanding,
    resume: ResumeProfileDocument | None,
    reference_provider: ReferenceProvider,
) -> ReferenceAnswer:
    question_text = topic.question_text or topic.main_question
    context = reference_provider.build_context(topic=topic, resume=resume)
    must_hit_points = question_understanding.expected_points[:4]
    answer_framework = _answer_framework(topic.topic_type)
    resume_stack = ", ".join(resume.tech_stack[:4]) if resume and resume.tech_stack else ""

    standard = _compose_reference_answer(
        question_text=question_text,
        must_hit_points=must_hit_points,
        guidance=context.bullet_points[:2],
        resume_stack="",
    )
    personalized = _compose_reference_answer(
        question_text=question_text,
        must_hit_points=must_hit_points,
        guidance=context.bullet_points[:3],
        resume_stack=resume_stack,
    )

    return ReferenceAnswer(
        reference_standard=standard,
        reference_personalized=personalized,
        must_hit_points=must_hit_points,
        answer_framework=answer_framework,
        sources=context.sources,
    )


def _heuristic_topic_evaluation(
    topic: TopicGroup,
    *,
    resume: ResumeProfileDocument | None,
    reference_answer: ReferenceAnswer,
    question_understanding: QuestionUnderstanding,
    evidence_items: list[EvidenceSnippet],
) -> TopicEvaluationDraft:
    candidate_text = _candidate_text(topic)
    rubric = _rubric(
        topic,
        candidate_text=candidate_text,
        expected_points=question_understanding.expected_points,
        resume=resume,
    )
    return TopicEvaluationDraft(
        question_understanding=question_understanding,
        rubric=rubric,
        strengths=_strengths(topic, rubric, candidate_text),
        weaknesses=_weaknesses(topic, rubric, candidate_text, reference_answer.must_hit_points),
        evidence_quotes=_evidence_quotes_from_items(evidence_items),
    )


def _merge_reference_answer(fallback: ReferenceAnswer, llm_result: ReferenceAnswer | None) -> ReferenceAnswer:
    if llm_result is None:
        return fallback
    merged = llm_result.model_copy(deep=True)
    if not merged.reference_standard:
        merged.reference_standard = fallback.reference_standard
    if not merged.reference_personalized:
        merged.reference_personalized = fallback.reference_personalized
    if not merged.must_hit_points:
        merged.must_hit_points = fallback.must_hit_points
    if not merged.answer_framework:
        merged.answer_framework = fallback.answer_framework
    if not merged.sources:
        merged.sources = fallback.sources
    return merged


def _merge_topic_evaluation(
    fallback: TopicEvaluationDraft,
    llm_result: TopicEvaluationDraft | None,
) -> TopicEvaluationDraft:
    if llm_result is None:
        return fallback
    merged = llm_result.model_copy(deep=True)
    if not merged.question_understanding.skill_tested:
        merged.question_understanding.skill_tested = fallback.question_understanding.skill_tested
    if not merged.question_understanding.expected_points:
        merged.question_understanding.expected_points = fallback.question_understanding.expected_points
    if not merged.strengths:
        merged.strengths = fallback.strengths
    if not merged.weaknesses:
        merged.weaknesses = fallback.weaknesses
    if not merged.evidence_quotes:
        merged.evidence_quotes = fallback.evidence_quotes
    if not merged.rubric.reasoning:
        merged.rubric.reasoning = fallback.rubric.reasoning
    return merged


def _compose_reference_answer(
    *,
    question_text: str,
    must_hit_points: list[str],
    guidance: list[str],
    resume_stack: str,
) -> str:
    lines = [f"For the question '{question_text}', I would answer it directly first and then support it with concrete reasoning."]
    if resume_stack:
        lines.append(f"I would anchor the answer in real stack evidence such as {resume_stack}.")
    for point in must_hit_points[:3]:
        lines.append(f"I would explicitly cover: {point}.")
    if guidance:
        lines.append(f"I would also make sure the answer reflects this expectation: {guidance[0]}.")
    lines.append("I would close with a concrete result, measurable change, or reflection so the answer does not stay abstract.")
    return "\n".join(lines)


def _candidate_text(topic: TopicGroup) -> str:
    parts = []
    if topic.answer_text:
        parts.append(topic.answer_text)
    parts.extend(followup.answer for followup in topic.followups if followup.answer)
    if parts:
        return "\n".join(part.strip() for part in parts if part and part.strip())
    return "\n".join(turn.text.strip() for turn in topic.exchanges if turn.role.value == "candidate").strip()


def _skill_tested(topic: TopicGroup) -> list[str]:
    combined = "\n".join(
        [
            topic.question_text or topic.main_question,
            topic.answer_text or "",
            *(followup.question for followup in topic.followups),
            *(followup.answer or "" for followup in topic.followups),
        ]
    ).lower()
    skills: list[str] = []
    for skill_name, keywords, _ in SKILL_RULES:
        if any(keyword.lower() in combined for keyword in keywords):
            skills.append(skill_name)
    if not skills:
        skills.append(topic.topic_type)
    return skills[:4]


def _expected_points(topic: TopicGroup, skills: list[str]) -> list[str]:
    points: list[str] = []
    for skill_name in skills:
        for rule_name, _, expected_points in SKILL_RULES:
            if rule_name == skill_name:
                points.extend(expected_points)
    if not points:
        if topic.topic_type == "behavioral":
            points = ["context", "action", "result and reflection"]
        elif topic.topic_type == "hr":
            points = ["clear motivation", "consistent expectation", "stable communication"]
        else:
            points = ["direct answer", "key detail", "case or result"]
    return _dedupe(points)[:5]


def _answer_framework(topic_type: str) -> list[str]:
    if topic_type == "technical":
        return ["conclusion", "mechanism", "trade-off", "result"]
    if topic_type == "project":
        return ["background", "ownership", "decision", "result"]
    if topic_type == "behavioral":
        return ["context", "task", "action", "result"]
    if topic_type == "hr":
        return ["conclusion", "motivation", "future expectation"]
    return ["direct answer", "supporting points", "result"]


def _rubric(
    topic: TopicGroup,
    *,
    candidate_text: str,
    expected_points: list[str],
    resume: ResumeProfileDocument | None,
) -> RubricScore:
    normalized = candidate_text.lower()
    answer_length = len(candidate_text)
    covered_points = sum(1 for point in expected_points if _covers_point(normalized, point))
    structure_hits = sum(1 for hint in STRUCTURE_HINTS if hint in candidate_text.lower())
    depth_hits = sum(1 for hint in DEPTH_HINTS if hint in candidate_text.lower())
    example_hits = sum(1 for hint in EXAMPLE_HINTS if hint in normalized)
    detail_penalty = 1 if any(hint in normalized for hint in LOW_DETAIL_HINTS) and answer_length < 120 else 0
    fit_hits = _resume_fit_hits(normalized, resume=resume)

    accuracy = _clamp_score(5 + covered_points + min(example_hits, 2) - detail_penalty)
    completeness = _clamp_score(4 + min(answer_length // 45, 4) + min(covered_points, 2))
    depth = _clamp_score(4 + min(depth_hits, 3) + min(example_hits, 2) - detail_penalty)
    structure = _clamp_score(4 + min(structure_hits, 3) + (1 if "\n" in candidate_text else 0))
    position_fit = _clamp_score(5 + min(fit_hits, 3) + (1 if topic.topic_type in {"technical", "project"} else 0))

    followup_handling = None
    if topic.has_followup:
        answered_followups = sum(1 for followup in topic.followups if followup.answer)
        followup_handling = _clamp_score(4 + min(answered_followups, 3) + min(depth_hits, 2))

    return RubricScore(
        accuracy=accuracy,
        completeness=completeness,
        depth=depth,
        structure=structure,
        position_fit=position_fit,
        followup_handling=followup_handling,
        reasoning=(
            f"candidate_chars={answer_length}, covered_points={covered_points}, "
            f"depth_hits={depth_hits}, structure_hits={structure_hits}, fit_hits={fit_hits}"
        ),
    )


def _covers_point(answer_text: str, point: str) -> bool:
    point_map = {
        "usage scenario": ("scenario", "\u573a\u666f", "\u7528\u4e8e", "\u7528\u6765"),
        "invalidation or consistency strategy": ("\u4e00\u81f4\u6027", "\u5931\u6548", "\u8fc7\u671f", "\u53cc\u5199"),
        "concurrency risk and fallback": ("\u5e76\u53d1", "\u9501", "\u91cd\u8bd5", "\u964d\u7ea7", "\u515c\u5e95", "\u5f02\u5e38"),
        "data model or query path": ("\u8868", "sql", "\u67e5\u8be2", "\u7d22\u5f15"),
        "performance optimization": ("\u4f18\u5316", "\u6027\u80fd", "\u538b\u6d4b", "\u7f13\u5b58"),
        "transaction or consistency handling": ("\u4e8b\u52a1", "\u4e00\u81f4\u6027", "\u56de\u6eda"),
        "task decomposition": ("\u62c6\u5206", "\u6a21\u5757", "\u8282\u70b9", "\u524d\u7aef", "\u540e\u7aef"),
        "state flow or orchestration": ("\u72b6\u6001", "\u8c03\u5ea6", "\u56de\u8df3"),
        "why this pattern fits the scenario": ("\u9002\u5408", "\u573a\u666f", "\u539f\u56e0", "because"),
        "baseline quality or problem": ("\u539f\u59cb", "\u6700\u5f00\u59cb", "\u95ee\u9898", "64%"),
        "optimization levers": ("\u4f18\u5316", "\u5904\u7406", "\u5207\u5757", "\u53c2\u6570", "\u91cd\u6392", "ocr"),
        "validation method or measurable result": ("\u51c6\u786e\u7387", "\u6307\u6807", "\u7ed3\u679c", "%"),
        "project background": ("\u80cc\u666f", "\u573a\u666f", "\u4e1a\u52a1"),
        "personal ownership": ("\u8d1f\u8d23", "\u6211\u505a", "\u4e3b\u5bfc", "\u63a8\u8fdb"),
        "key decision and outcome": ("\u51b3\u7b56", "\u53d6\u820d", "\u7ed3\u679c", "\u6548\u679c"),
        "context": ("\u80cc\u666f", "\u5f53\u65f6", "\u573a\u666f"),
        "action": ("\u505a\u4e86", "\u63a8\u8fdb", "\u6c9f\u901a"),
        "result and reflection": ("\u7ed3\u679c", "\u590d\u76d8", "\u603b\u7ed3"),
        "clear motivation": ("\u52a8\u673a", "\u539f\u56e0"),
        "consistent expectation": ("\u4e00\u81f4", "\u9884\u671f", "\u89c4\u5212"),
        "stable communication": ("\u7a33\u5b9a", "\u6e05\u695a", "\u771f\u5b9e"),
        "direct answer": ("core", "\u6838\u5fc3", "\u4e3b\u8981"),
        "key detail": ("\u5177\u4f53", "\u7ec6\u8282", "\u4f8b\u5982", "\u6bd4\u5982"),
        "case or result": ("\u6848\u4f8b", "\u7ed3\u679c", "\u6307\u6807", "\u9879\u76ee"),
    }
    return any(keyword in answer_text for keyword in point_map.get(point, ()))


def _resume_fit_hits(answer_text: str, *, resume: ResumeProfileDocument | None) -> int:
    if resume is None:
        return 0
    return sum(1 for tech in resume.tech_stack[:6] if tech.lower() in answer_text)


def _strengths(topic: TopicGroup, rubric: RubricScore, candidate_text: str) -> list[str]:
    strengths: list[str] = []
    if rubric.accuracy >= 7:
        strengths.append("The answer covers the core of the question.")
    if rubric.depth >= 7:
        strengths.append("The answer explains principle, trade-off, or risk handling.")
    if rubric.structure >= 7:
        strengths.append("The answer is reasonably structured.")
    if topic.has_followup and (rubric.followup_handling or 0) >= 7:
        strengths.append("The answer remains stable under follow-up pressure.")
    if len(candidate_text) >= 120:
        strengths.append("The answer carries enough information density.")
    return strengths or ["The answer broadly points in the right direction."]


def _weaknesses(
    topic: TopicGroup,
    rubric: RubricScore,
    candidate_text: str,
    must_hit_points: list[str],
) -> list[str]:
    weaknesses: list[str] = []
    if rubric.completeness <= 6:
        weaknesses.append("The answer lacks enough supporting detail.")
    if rubric.depth <= 6:
        weaknesses.append("The answer does not explain enough principle, trade-off, or quantified detail.")
    if rubric.structure <= 6:
        weaknesses.append("The answer could be organized more clearly.")
    if rubric.position_fit <= 6:
        weaknesses.append("The answer does not stay close enough to the question's scenario.")
    if topic.has_followup and (rubric.followup_handling or 0) <= 6:
        weaknesses.append("Follow-up handling is still shallow.")
    if len(candidate_text) < 60:
        weaknesses.append("The answer is short and under-supported.")
    missing_points = [point for point in must_hit_points if not _covers_point(candidate_text.lower(), point)]
    if missing_points:
        weaknesses.append(f"One key coverage point is still weak: {missing_points[0]}.")
    return _dedupe(weaknesses)[:4] or ["Adding measurable outcomes would make the answer more convincing."]


def _evidence_items(topic: TopicGroup, limit: int = 3) -> list[EvidenceSnippet]:
    snippets: list[EvidenceSnippet] = []
    preferred_turn_ids = set(topic.answer_turn_ids)

    candidate_turns = [
        turn
        for turn in topic.exchanges
        if turn.role.value == "candidate"
        and turn.text.strip()
        and (not preferred_turn_ids or turn.turn_id in preferred_turn_ids)
    ]
    if not candidate_turns:
        candidate_turns = [
            turn
            for turn in topic.exchanges
            if turn.role.value == "candidate" and turn.text.strip()
        ]

    for turn in candidate_turns[:limit]:
        snippets.append(
            EvidenceSnippet(
                text=turn.text.strip(),
                speaker_role=turn.role,
                start_ms=turn.start_ms,
                end_ms=turn.end_ms,
                turn_id=turn.turn_id,
            )
        )

    if snippets:
        return snippets

    if topic.answer_text:
        for paragraph in [part.strip() for part in topic.answer_text.split("\n") if part.strip()][:limit]:
            snippets.append(EvidenceSnippet(text=paragraph))
    return snippets


def _evidence_quotes_from_items(items: list[EvidenceSnippet]) -> list[str]:
    quotes: list[str] = []
    for item in items:
        text = item.text.strip()
        if not text:
            continue
        quotes.append(text[:120] + ("..." if len(text) > 120 else ""))
    return quotes[:3]


def _clamp_score(score: int) -> int:
    return max(1, min(10, score))


def _dedupe(items: list[str]) -> list[str]:
    counter = Counter(item.strip() for item in items if item.strip())
    return [item for item, _ in counter.most_common()]
