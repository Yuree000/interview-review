from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from core.time_utils import utc_now_iso


SCHEMA_VERSION = "1.0"
DEFAULT_STAGE_ORDER = ("A1", "A2", "B1", "B2", "B3", "B4", "B5", "B6")


class AppBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class StageStatus(StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class PipelineStatus(StrEnum):
    pending = "pending"
    preprocessing = "preprocessing"
    analyzing = "analyzing"
    completed = "completed"
    failed = "failed"


class SpeakerRole(StrEnum):
    interviewer = "interviewer"
    candidate = "candidate"
    unknown = "unknown"


def default_stage_map() -> dict[str, StageStatus]:
    return {stage: StageStatus.pending for stage in DEFAULT_STAGE_ORDER}


class StatusDocument(AppBaseModel):
    schema_version: str = SCHEMA_VERSION
    interview_id: str
    status: PipelineStatus = PipelineStatus.pending
    current_stage: str = DEFAULT_STAGE_ORDER[0]
    stages: dict[str, StageStatus] = Field(default_factory=default_stage_map)
    last_error: str | None = None
    started_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class InterviewMetaDocument(AppBaseModel):
    schema_version: str = SCHEMA_VERSION
    interview_id: str
    title: str
    source_file_name: str
    source_file_path: str | None = None
    input_type: Literal["audio", "video", "unknown"] = "unknown"
    target_position: str | None = None
    direction: str | None = None
    duration_seconds: int | None = None
    file_size_bytes: int | None = None
    notes: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class ResumeProject(AppBaseModel):
    name: str
    role: str | None = None
    highlights: list[str] = Field(default_factory=list)


class ResumeProfileDocument(AppBaseModel):
    schema_version: str = SCHEMA_VERSION
    name: str | None = None
    target_positions: list[str] = Field(default_factory=list)
    years_of_experience: float | None = None
    tech_stack: list[str] = Field(default_factory=list)
    education: str | None = None
    key_projects: list[ResumeProject] = Field(default_factory=list)
    raw_text: str | None = None
    updated_at: str = Field(default_factory=utc_now_iso)


class WordTimestamp(AppBaseModel):
    word: str
    start_ms: int | None = None
    end_ms: int | None = None


class TranscriptSegment(AppBaseModel):
    segment_id: str
    speaker_id: str
    role: SpeakerRole = SpeakerRole.unknown
    start_ms: int | None = None
    end_ms: int | None = None
    text: str
    confidence: float | None = None
    words: list[WordTimestamp] = Field(default_factory=list)


class TranscriptionDocument(AppBaseModel):
    schema_version: str = SCHEMA_VERSION
    interview_id: str
    source_audio_path: str | None = None
    source_video_path: str | None = None
    language: str = "zh-CN"
    speaker_count: int | None = None
    asr_task_id: str | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)
    raw_response: dict[str, Any] | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class DialogueTurn(AppBaseModel):
    turn_id: str | None = None
    speaker_id: str
    role: SpeakerRole = SpeakerRole.unknown
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    source_segment_ids: list[str] = Field(default_factory=list)


class FollowupPair(AppBaseModel):
    question: str
    answer: str | None = None
    question_turn_ids: list[str] = Field(default_factory=list)
    answer_turn_ids: list[str] = Field(default_factory=list)


class TopicGroup(AppBaseModel):
    topic_id: int
    main_question: str
    question_text: str | None = None
    question_turn_ids: list[str] = Field(default_factory=list)
    answer_text: str | None = None
    answer_turn_ids: list[str] = Field(default_factory=list)
    followups: list[FollowupPair] = Field(default_factory=list)
    turn_ids: list[str] = Field(default_factory=list)
    topic_summary: str
    topic_type: Literal["technical", "behavioral", "project", "hr", "other"] = "other"
    exchange_count: int = 0
    has_followup: bool = False
    boundary_confidence: float | None = None
    split_reason: list[str] = Field(default_factory=list)
    exchanges: list[DialogueTurn] = Field(default_factory=list)


class QaPairsDocument(AppBaseModel):
    schema_version: str = SCHEMA_VERSION
    interview_id: str
    topics: list[TopicGroup] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class QuestionUnderstanding(AppBaseModel):
    question_type: str
    skill_tested: list[str] = Field(default_factory=list)
    expected_points: list[str] = Field(default_factory=list)


class RubricScore(AppBaseModel):
    accuracy: int = Field(ge=1, le=10)
    completeness: int = Field(ge=1, le=10)
    depth: int = Field(ge=1, le=10)
    structure: int = Field(ge=1, le=10)
    position_fit: int = Field(ge=1, le=10)
    followup_handling: int | None = Field(default=None, ge=1, le=10)
    reasoning: str = ""

    def weighted_total(self) -> float:
        weighted_sum = (
            self.accuracy * 0.2
            + self.completeness * 0.2
            + self.depth * 0.25
            + self.structure * 0.15
            + self.position_fit * 0.2
        )
        total_weight = 1.0
        if self.followup_handling is not None:
            weighted_sum += self.followup_handling * 0.1
            total_weight += 0.1
        return round((weighted_sum / total_weight), 1)


class ReferenceSource(AppBaseModel):
    title: str
    url: str | None = None
    source_type: Literal["knowledge_base", "web_search", "other"] = "other"


class ReferenceAnswer(AppBaseModel):
    reference_standard: str
    reference_personalized: str
    must_hit_points: list[str] = Field(default_factory=list)
    answer_framework: list[str] = Field(default_factory=list)
    sources: list[ReferenceSource] = Field(default_factory=list)


class TopicAnalysis(AppBaseModel):
    topic_id: int
    main_question: str
    question_understanding: QuestionUnderstanding
    rubric: RubricScore
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)
    reference_answer: ReferenceAnswer | None = None


class InterviewSummary(AppBaseModel):
    overall_summary: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    confidence_notes: list[str] = Field(default_factory=list)
    action_plan_7d: list[str] = Field(default_factory=list)
    average_scores: dict[str, float] = Field(default_factory=dict)


class AnalysesDocument(AppBaseModel):
    schema_version: str = SCHEMA_VERSION
    interview_id: str
    analyses: list[TopicAnalysis] = Field(default_factory=list)
    summary: InterviewSummary | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class CapabilitySnapshotDocument(AppBaseModel):
    schema_version: str = SCHEMA_VERSION
    interview_id: str
    public_dimensions: dict[str, float] = Field(default_factory=dict)
    role_dimensions: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    next_focus: list[str] = Field(default_factory=list)
    summary: str = ""
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class GlobalProfileDocument(AppBaseModel):
    schema_version: str = SCHEMA_VERSION
    public_dimensions: dict[str, float] = Field(default_factory=dict)
    role_dimensions: dict[str, dict[str, float]] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    learning_roadmap: list[str] = Field(default_factory=list)
    trend_summary: str = ""
    generated_at: str = Field(default_factory=utc_now_iso)


class CompareResultDocument(AppBaseModel):
    schema_version: str = SCHEMA_VERSION
    interview_id_a: str
    interview_id_b: str
    improvements: list[str] = Field(default_factory=list)
    regressions: list[str] = Field(default_factory=list)
    repeated_issues: list[str] = Field(default_factory=list)
    next_focus: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=utc_now_iso)
