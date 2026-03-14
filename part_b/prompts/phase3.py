from __future__ import annotations

import json
from typing import Any


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _dump_lines(lines: list[str]) -> str:
    return "\n".join(lines)


ROLE_IDENTIFIER_SYSTEM_PROMPT = """You analyze Chinese interview transcripts.
Return JSON only.
You must assign each speaker to one role:
- interviewer
- candidate
- unknown
Preserve every speaker_id from the input.
"""


def build_role_identifier_prompt(
    *,
    speaker_stats: list[dict[str, Any]],
    transcript_excerpt: list[dict[str, Any]],
    meta: dict[str, Any],
    resume: dict[str, Any] | None,
) -> str:
    return (
        "Determine speaker roles for this interview transcript.\n"
        "Prefer evidence from question patterns, answer length, and conversation order.\n"
        "Return JSON with shape:\n"
        '{"assignments":[{"speaker_id":"0","role":"interviewer","confidence":0.9,"reason":"..."}],"summary":"..."}\n\n'
        f"meta=\n{_dump(meta)}\n\n"
        f"resume=\n{_dump(resume or {})}\n\n"
        f"speaker_stats=\n{_dump(speaker_stats)}\n\n"
        f"transcript_excerpt=\n{_dump(transcript_excerpt)}"
    )


CONTEXT_COMPLETER_SYSTEM_PROMPT = """You enrich interview context for later analysis.
Return JSON only.
Infer a practical target_position and direction from transcript evidence and resume context.
"""


def build_context_completion_prompt(
    *,
    meta: dict[str, Any],
    resume: dict[str, Any] | None,
    role_summary: dict[str, Any],
    transcript_excerpt: list[dict[str, Any]],
) -> str:
    return (
        "Complete the interview context.\n"
        "Return JSON with shape:\n"
        '{"target_position":"...","direction":"...","notes":["...","..."]}\n\n'
        f"meta=\n{_dump(meta)}\n\n"
        f"resume=\n{_dump(resume or {})}\n\n"
        f"role_summary=\n{_dump(role_summary)}\n\n"
        f"transcript_excerpt=\n{_dump(transcript_excerpt)}"
    )


QA_EXTRACTOR_SYSTEM_PROMPT = """You extract review-worthy QA pairs from a full Chinese interview transcript.
Your output must be grounded in real interviewer questions from the transcript.
You are not grading, summarizing the whole interview, or generating reference answers.
Return JSON only. Do not include explanations or chain-of-thought.
"""


def build_qa_extractor_prompt(*, transcript_lines: list[str]) -> str:
    return (
        "Read the full interview transcript below and extract 8 to 14 review-worthy QA pairs.\n\n"
        "Goal:\n"
        "- Keep only questions that are genuinely valuable for interview review.\n"
        "- Record the candidate's corresponding answer faithfully.\n\n"
        "Hard rules:\n"
        "1. Every QA pair must be anchored to a real interviewer question.\n"
        "2. question_turn_ids may contain interviewer turns only.\n"
        "3. answer_turn_ids may contain candidate turns only.\n"
        "4. The question text must be a faithful rewrite of those interviewer turns. Do not invent summary questions.\n"
        "5. Never output generic invented questions such as:\n"
        "   - What AI tools did the candidate mention?\n"
        "   - What technologies did the candidate mention?\n"
        "   - What strategies did the candidate mention?\n"
        "6. Keep high-value questions only: project ownership, system design, technical implementation, metrics/optimization, trade-offs, tool boundaries, behavior/judgment.\n"
        "7. Ignore low-value content: greetings, audio/video checks, process explanation, thesis status, graduation logistics, join date, salary, conversion policy, team size, candidate reverse questions, closing chat.\n"
        "8. If an interviewer uses a short warm-up/confirmation sentence before the real question, keep the real question only.\n"
        "9. If follow-up questions test different competencies, split them into separate QA pairs.\n"
        "10. If follow-up turns only clarify the same competency, you may merge them into one answer.\n"
        "11. The answer must stay faithful to what the candidate actually said. Do not upgrade it into an ideal answer.\n"
        "12. If a framework or tool name is clearly an ASR homophone and the intended standard name is obvious from context, normalize it. Examples: Agent, LangChain, LangGraph, Cloud Code, RAG. Do not guess when uncertain.\n"
        "13. Do not assume a target job direction.\n"
        "14. Preserve interview order.\n"
        "15. Be selective. Fewer high-value QA pairs are better than noisy coverage.\n\n"
        "Return JSON with this shape:\n"
        "{\n"
        '  "qa_pairs": [\n'
        "    {\n"
        '      "qa_id": 1,\n'
        '      "question_turn_ids": ["t12"],\n'
        '      "answer_turn_ids": ["t13", "t14"],\n'
        '      "question": "Why did you decide not to stay at your current company?",\n'
        '      "answer": "The candidate said the current company mainly builds internal efficiency tools, which conflicts with the long-term direction they want to invest in.",\n'
        '      "topic_type": "behavioral"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "transcript=\n"
        f"{_dump_lines(transcript_lines)}"
    )
