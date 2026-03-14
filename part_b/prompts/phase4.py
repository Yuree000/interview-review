from __future__ import annotations

import json
from typing import Any


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


REFERENCE_ANSWER_SYSTEM_PROMPT = """You are a Chinese interview coach.
Generate a high-quality reference answer for one interview question.
Return JSON only. Do not include explanations or chain-of-thought.
The reference answer must read like something the candidate could actually say out loud.
"""


def build_reference_answer_prompt(
    *,
    meta: dict[str, Any],
    resume: dict[str, Any] | None,
    topic: dict[str, Any],
    reference_context: dict[str, Any],
) -> str:
    return (
        "Generate a high-quality Chinese reference answer for this interview topic.\n\n"
        "Requirements:\n"
        "1. reference_standard must be a direct, speakable answer, not coaching instructions.\n"
        "2. reference_personalized may adapt to explicit candidate background, but must not invent projects, metrics, or responsibilities.\n"
        "3. If the question does not explicitly constrain a job direction, do not force the answer into a fixed role framing.\n"
        "4. must_hit_points should contain 3 to 6 concrete coverage points.\n"
        "5. answer_framework should be a short outline only.\n"
        "6. If a framework or tool name is clearly an ASR homophone and the intended standard name is obvious from context, normalize it. Examples: Agent, LangChain, LangGraph, Cloud Code, RAG. Do not guess when uncertain.\n"
        "7. The answer should show reasoning, trade-offs, and result awareness, not generic filler.\n\n"
        "Return JSON with this shape:\n"
        "{\n"
        '  "reference_standard": "...",\n'
        '  "reference_personalized": "...",\n'
        '  "must_hit_points": ["..."],\n'
        '  "answer_framework": ["..."],\n'
        '  "sources": [{"title": "...", "url": null, "source_type": "knowledge_base"}]\n'
        "}\n\n"
        f"resume=\n{_dump(resume or {})}\n\n"
        f"topic=\n{_dump(topic)}\n\n"
        f"reference_context=\n{_dump(reference_context)}"
    )


TOPIC_EVALUATION_SYSTEM_PROMPT = """You evaluate one Chinese interview answer against a reference answer.
Return JSON only. Do not include explanations or chain-of-thought.
"""


def build_topic_evaluation_prompt(
    *,
    meta: dict[str, Any],
    resume: dict[str, Any] | None,
    topic: dict[str, Any],
    reference_answer: dict[str, Any],
) -> str:
    return (
        "Evaluate the candidate's answer quality for this interview topic.\n\n"
        "Requirements:\n"
        "1. expected_points must come from the question and the reference answer.\n"
        "2. strengths and weaknesses must be grounded in the actual candidate answer.\n"
        "3. evidence_quotes must quote or tightly paraphrase the actual answer.\n"
        "4. Scores must stay between 1 and 10.\n\n"
        "Return JSON with this shape:\n"
        "{\n"
        '  "question_understanding": {"question_type": "technical", "skill_tested": ["..."], "expected_points": ["..."]},\n'
        '  "rubric": {"accuracy": 7, "completeness": 7, "depth": 7, "structure": 7, "position_fit": 7, "followup_handling": 7, "reasoning": "..."},\n'
        '  "strengths": ["..."],\n'
        '  "weaknesses": ["..."],\n'
        '  "evidence_quotes": ["..."]\n'
        "}\n\n"
        f"resume=\n{_dump(resume or {})}\n\n"
        f"topic=\n{_dump(topic)}\n\n"
        f"reference_answer=\n{_dump(reference_answer)}"
    )


INTERVIEW_SUMMARY_SYSTEM_PROMPT = """You summarize interview analyses into an actionable Chinese coaching summary.
Return JSON only.
The average_scores object should use concise numeric values.
"""


def build_interview_summary_prompt(
    *,
    meta: dict[str, Any],
    analyses: list[dict[str, Any]],
) -> str:
    return (
        "Summarize this interview review and return JSON with shape:\n"
        "{"
        '"overall_summary":"...",'
        '"strengths":["..."],'
        '"weaknesses":["..."],'
        '"confidence_notes":["..."],'
        '"action_plan_7d":["..."],'
        '"average_scores":{"accuracy":7.5,"completeness":7.0,"weighted_total":7.2}'
        "}\n\n"
        f"meta=\n{_dump(meta)}\n\n"
        f"analyses=\n{_dump(analyses)}"
    )
