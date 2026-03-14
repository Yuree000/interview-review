from __future__ import annotations

from typing import TypedDict

from part_b.schemas import InterviewMetaDocument, QaPairsDocument, ResumeProfileDocument, TranscriptionDocument


class Phase3State(TypedDict, total=False):
    interview_id: str
    transcription: TranscriptionDocument
    meta: InterviewMetaDocument
    resume_profile: ResumeProfileDocument | None
    role_result: dict
    context_result: dict
    qa_pairs: QaPairsDocument
