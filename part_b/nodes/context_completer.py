from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from part_b.llm_utils import safe_invoke_json_model
from part_b.nodes.role_identifier import RoleIdentificationResult
from part_b.prompts.phase3 import CONTEXT_COMPLETER_SYSTEM_PROMPT, build_context_completion_prompt
from part_b.schemas import InterviewMetaDocument, ResumeProfileDocument, TranscriptionDocument


DIRECTION_KEYWORDS = {
    "backend": ("java", "spring", "mysql", "redis", "kafka", "rabbitmq", "microservice", "api", "sql", "cache"),
    "frontend": ("react", "vue", "javascript", "typescript", "css", "html", "browser", "component"),
    "data-ai": ("algorithm", "model", "training", "feature", "machine learning", "ai", "recommendation", "llm"),
    "mobile": ("android", "ios", "flutter", "react native"),
    "qa": ("testing", "test case", "qa", "automation", "selenium"),
}


class ContextCompletionResult(BaseModel):
    target_position: str | None = None
    direction: str | None = None
    notes: list[str] = Field(default_factory=list)
    strategy: str = "heuristic"


def _resume_target_position(resume: ResumeProfileDocument | None) -> str | None:
    if resume is None:
        return None
    return resume.target_positions[0] if resume.target_positions else None


def _combined_text(document: TranscriptionDocument, resume: ResumeProfileDocument | None) -> str:
    parts = [segment.text for segment in document.segments]
    if resume is not None:
        parts.extend(resume.tech_stack)
        parts.extend(project.name for project in resume.key_projects)
        if resume.raw_text:
            parts.append(resume.raw_text)
    return "\n".join(parts).lower()


def _infer_direction(document: TranscriptionDocument, resume: ResumeProfileDocument | None) -> str | None:
    combined = _combined_text(document, resume)
    scores = Counter()
    for direction, keywords in DIRECTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in combined:
                scores[direction] += 1
    if not scores:
        return None
    return scores.most_common(1)[0][0]


def _infer_target_position(meta: InterviewMetaDocument | None, direction: str | None) -> str | None:
    if meta is not None and meta.target_position:
        return meta.target_position
    mapping = {
        "backend": "Backend Developer",
        "frontend": "Frontend Developer",
        "data-ai": "Data / AI Engineer",
        "mobile": "Mobile Developer",
        "qa": "QA Engineer",
    }
    return mapping.get(direction, "Software Engineer" if direction else None)


def _heuristic_notes(
    *,
    resume: ResumeProfileDocument | None,
    direction: str | None,
) -> list[str]:
    notes: list[str] = []
    if resume is not None and resume.tech_stack:
        notes.append(f"resume tech stack: {', '.join(resume.tech_stack[:8])}")
    if resume is not None and resume.years_of_experience is not None:
        notes.append(f"resume experience years: {resume.years_of_experience}")
    if direction:
        notes.append(f"inferred direction: {direction}")
    return notes


def _llm_result(
    *,
    document: TranscriptionDocument,
    meta: InterviewMetaDocument | None,
    resume: ResumeProfileDocument | None,
    role_result: RoleIdentificationResult | None,
) -> ContextCompletionResult | None:
    excerpt = [
        {
            "speaker_id": segment.speaker_id,
            "role": segment.role.value,
            "text": segment.text,
        }
        for segment in document.segments[:20]
    ]
    return safe_invoke_json_model(
        ContextCompletionResult,
        system_prompt=CONTEXT_COMPLETER_SYSTEM_PROMPT,
        user_prompt=build_context_completion_prompt(
            meta=meta.model_dump(mode="json") if meta else {},
            resume=resume.model_dump(mode="json") if resume else None,
            role_summary=role_result.model_dump(mode="json") if role_result else {},
            transcript_excerpt=excerpt,
        ),
        temperature=0.6,
        max_tokens=2048,
    )


def apply_context_completion(
    meta: InterviewMetaDocument,
    result: ContextCompletionResult,
) -> InterviewMetaDocument:
    updated = meta.model_copy(deep=True)
    if result.target_position:
        updated.target_position = result.target_position
    if result.direction:
        updated.direction = result.direction
    if result.notes:
        updated.notes = "\n".join(f"- {item}" for item in result.notes)
    return updated


def complete_context(
    document: TranscriptionDocument,
    *,
    meta: InterviewMetaDocument,
    resume: ResumeProfileDocument | None = None,
    role_result: RoleIdentificationResult | None = None,
) -> tuple[ContextCompletionResult, InterviewMetaDocument]:
    inferred_direction = meta.direction or _infer_direction(document, resume)
    inferred_target_position = meta.target_position or _resume_target_position(resume) or _infer_target_position(
        meta,
        inferred_direction,
    )
    heuristic_result = ContextCompletionResult(
        target_position=inferred_target_position,
        direction=inferred_direction,
        notes=_heuristic_notes(resume=resume, direction=inferred_direction),
        strategy="heuristic",
    )

    llm_result = _llm_result(
        document=document,
        meta=meta,
        resume=resume,
        role_result=role_result,
    )
    result = llm_result or heuristic_result
    if not result.target_position:
        result.target_position = heuristic_result.target_position
    if not result.direction:
        result.direction = heuristic_result.direction
    if not result.notes:
        result.notes = heuristic_result.notes
    if llm_result is not None:
        result.strategy = "llm+heuristic"

    updated_meta = apply_context_completion(meta, result)
    return result, updated_meta
