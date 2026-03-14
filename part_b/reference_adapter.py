from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from part_b.schemas import InterviewMetaDocument, ReferenceSource, ResumeProfileDocument, TopicGroup


@dataclass
class ReferenceContext:
    bullet_points: list[str]
    sources: list[ReferenceSource]


class ReferenceProvider(Protocol):
    def build_context(
        self,
        *,
        topic: TopicGroup,
        meta: InterviewMetaDocument | None = None,
        resume: ResumeProfileDocument | None = None,
    ) -> ReferenceContext: ...


class LocalHeuristicReferenceProvider:
    def build_context(
        self,
        *,
        topic: TopicGroup,
        meta: InterviewMetaDocument | None = None,
        resume: ResumeProfileDocument | None = None,
    ) -> ReferenceContext:
        bullet_points = _topic_guidance(topic)
        bullet_points.extend(_question_guidance(topic))

        if resume and resume.tech_stack:
            bullet_points.append(
                f"If the candidate already has explicit stack evidence, it is valid to anchor the answer in: {', '.join(resume.tech_stack[:6])}."
            )
        if topic.answer_text:
            bullet_points.append(
                "The reference answer should patch missing high-value details from the real answer, not merely rewrite the same wording."
            )

        return ReferenceContext(
            bullet_points=_dedupe_preserve_order(bullet_points),
            sources=[ReferenceSource(title="Local interview heuristics", source_type="knowledge_base")],
        )


def get_default_reference_provider() -> ReferenceProvider:
    return LocalHeuristicReferenceProvider()


def _topic_guidance(topic: TopicGroup) -> list[str]:
    if topic.topic_type == "technical":
        return [
            "Answer with a conclusion first, then explain mechanism, trade-offs, and risk handling.",
            "Add measurable outcomes, boundary conditions, or failure handling when possible.",
            "Do not stop at the implementation; explain why this design was chosen.",
        ]
    if topic.topic_type == "project":
        return [
            "State project background and personal ownership before detailing key decisions and outcomes.",
            "Highlight what the candidate personally drove instead of describing team work in general.",
            "If there were business or production results, make them explicit.",
        ]
    if topic.topic_type == "behavioral":
        return [
            "Keep a situation-action-result progression.",
            "Show judgment, action details, and reflection instead of attitude-only statements.",
            "Avoid generic claims; add concrete context or consequences.",
        ]
    if topic.topic_type == "hr":
        return [
            "Keep the answer stable, truthful, and internally consistent.",
            "Explain motivation and fit instead of only stating preference.",
        ]
    return [
        "Answer the question directly, then add two or three supporting points.",
        "Use examples, numbers, or concrete outcomes when available.",
    ]


def _question_guidance(topic: TopicGroup) -> list[str]:
    question = (topic.question_text or topic.main_question or "").lower()
    guidance: list[str] = []

    if any(token in question for token in ("\u4e3a\u4ec0\u4e48", "why", "\u53d6\u820d", "trade-off")):
        guidance.append("This answer must explain not just what was done, but why that choice was made and what alternatives were rejected.")
    if any(token in question for token in ("\u600e\u4e48", "\u5982\u4f55", "\u5c55\u5f00", "\u8bbe\u8ba1", "\u5b9e\u73b0")):
        guidance.append("This answer should unfold step-by-step or module-by-module, not as abstract statements.")
    if any(token in question for token in ("redis", "cache", "\u7f13\u5b58")):
        guidance.append("Cover usage scenario, invalidation strategy, concurrency risk, and fallback handling.")
    if any(token in question for token in ("mysql", "sql", "\u6570\u636e\u5e93")):
        guidance.append("Cover data model, query optimization, and transaction or consistency handling.")
    if any(token in question for token in ("langchain", "langgraph", "agent", "\u591aagent")):
        guidance.append("Explain task decomposition, state flow, orchestration boundary, and why this pattern fits the scenario.")
    if any(token in question for token in ("rag", "\u53ec\u56de", "\u5411\u91cf", "\u51c6\u786e\u7387")):
        guidance.append("Explain baseline quality, optimization levers, validation method, and headroom for further improvement.")
    if any(token in question for token in ("\u9879\u76ee", "project", "\u8d1f\u8d23", "\u843d\u5730")):
        guidance.append("Tie background, ownership, key actions, and measurable result into one coherent answer.")
    return guidance


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
