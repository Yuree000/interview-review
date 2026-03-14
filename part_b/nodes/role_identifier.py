from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from part_b.llm_utils import safe_invoke_json_model
from part_b.prompts.phase3 import ROLE_IDENTIFIER_SYSTEM_PROMPT, build_role_identifier_prompt
from part_b.schemas import InterviewMetaDocument, ResumeProfileDocument, SpeakerRole, TranscriptionDocument


QUESTION_HINTS = (
    "?",
    "吗",
    "么",
    "什么",
    "如何",
    "怎么",
    "为什么",
    "please",
    "introduce",
    "tell me",
    "explain",
)


@dataclass(frozen=True)
class SpeakerStats:
    speaker_id: str
    segment_count: int
    total_chars: int
    question_like_count: int
    first_index: int


class RoleAssignment(BaseModel):
    speaker_id: str
    role: SpeakerRole
    confidence: float = Field(default=0.5, ge=0, le=1)
    reason: str = ""


class RoleIdentificationResult(BaseModel):
    assignments: list[RoleAssignment]
    summary: str = ""
    strategy: str = "heuristic"


def _is_question_like(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in QUESTION_HINTS)


def _build_stats(document: TranscriptionDocument) -> list[SpeakerStats]:
    grouped: dict[str, dict] = {}
    for index, segment in enumerate(document.segments):
        speaker_id = segment.speaker_id
        bucket = grouped.setdefault(
            speaker_id,
            {
                "segment_count": 0,
                "total_chars": 0,
                "question_like_count": 0,
                "first_index": index,
            },
        )
        bucket["segment_count"] += 1
        bucket["total_chars"] += len(segment.text.strip())
        bucket["question_like_count"] += 1 if _is_question_like(segment.text) else 0
        bucket["first_index"] = min(bucket["first_index"], index)

    return [
        SpeakerStats(
            speaker_id=speaker_id,
            segment_count=data["segment_count"],
            total_chars=data["total_chars"],
            question_like_count=data["question_like_count"],
            first_index=data["first_index"],
        )
        for speaker_id, data in grouped.items()
    ]


def _heuristic_role_map(stats: list[SpeakerStats]) -> dict[str, SpeakerRole]:
    if not stats:
        return {}
    if len(stats) == 1:
        return {stats[0].speaker_id: SpeakerRole.unknown}

    interviewer = sorted(
        stats,
        key=lambda item: (-item.question_like_count, item.first_index, item.total_chars),
    )[0]
    candidate_pool = [item for item in stats if item.speaker_id != interviewer.speaker_id]
    candidate = sorted(
        candidate_pool,
        key=lambda item: (-item.total_chars, item.first_index),
    )[0] if candidate_pool else interviewer

    role_map = {item.speaker_id: SpeakerRole.unknown for item in stats}
    role_map[interviewer.speaker_id] = SpeakerRole.interviewer
    if candidate.speaker_id != interviewer.speaker_id:
        role_map[candidate.speaker_id] = SpeakerRole.candidate
    return role_map


def _stats_payload(stats: list[SpeakerStats]) -> list[dict]:
    return [
        {
            "speaker_id": item.speaker_id,
            "segment_count": item.segment_count,
            "total_chars": item.total_chars,
            "question_like_count": item.question_like_count,
            "first_index": item.first_index,
        }
        for item in stats
    ]


def _excerpt_payload(document: TranscriptionDocument, limit: int = 16) -> list[dict]:
    payload: list[dict] = []
    for segment in document.segments[:limit]:
        payload.append(
            {
                "speaker_id": segment.speaker_id,
                "role": segment.role.value,
                "text": segment.text,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
            }
        )
    return payload


def _llm_result(
    *,
    document: TranscriptionDocument,
    stats: list[SpeakerStats],
    meta: InterviewMetaDocument | None,
    resume: ResumeProfileDocument | None,
) -> RoleIdentificationResult | None:
    return safe_invoke_json_model(
        RoleIdentificationResult,
        system_prompt=ROLE_IDENTIFIER_SYSTEM_PROMPT,
        user_prompt=build_role_identifier_prompt(
            speaker_stats=_stats_payload(stats),
            transcript_excerpt=_excerpt_payload(document),
            meta=meta.model_dump(mode="json") if meta else {},
            resume=resume.model_dump(mode="json") if resume else None,
        ),
        temperature=0.6,
        max_tokens=2048,
    )


def _merge_role_map(
    stats: list[SpeakerStats],
    heuristic_map: dict[str, SpeakerRole],
    llm_result: RoleIdentificationResult | None,
) -> RoleIdentificationResult:
    assignments: list[RoleAssignment] = []
    llm_map = {
        item.speaker_id: item
        for item in (llm_result.assignments if llm_result is not None else [])
    }

    for stat in stats:
        llm_assignment = llm_map.get(stat.speaker_id)
        if llm_assignment is not None:
            assignments.append(llm_assignment)
            continue
        assignments.append(
            RoleAssignment(
                speaker_id=stat.speaker_id,
                role=heuristic_map.get(stat.speaker_id, SpeakerRole.unknown),
                confidence=0.55,
                reason="heuristic fallback",
            )
        )

    return RoleIdentificationResult(
        assignments=assignments,
        summary=llm_result.summary if llm_result is not None else "speaker roles inferred from transcript heuristics",
        strategy="llm+heuristic" if llm_result is not None else "heuristic",
    )


def apply_role_assignments(
    document: TranscriptionDocument,
    result: RoleIdentificationResult,
) -> TranscriptionDocument:
    role_map = {item.speaker_id: item.role for item in result.assignments}
    updated = document.model_copy(deep=True)
    for segment in updated.segments:
        segment.role = role_map.get(segment.speaker_id, SpeakerRole.unknown)
    return updated


def identify_roles(
    document: TranscriptionDocument,
    *,
    meta: InterviewMetaDocument | None = None,
    resume: ResumeProfileDocument | None = None,
) -> tuple[RoleIdentificationResult, TranscriptionDocument]:
    stats = _build_stats(document)
    heuristic_map = _heuristic_role_map(stats)
    llm_result = _llm_result(document=document, stats=stats, meta=meta, resume=resume)
    result = _merge_role_map(stats, heuristic_map, llm_result)
    updated_document = apply_role_assignments(document, result)
    return result, updated_document
