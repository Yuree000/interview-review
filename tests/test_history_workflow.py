from __future__ import annotations

from pathlib import Path

import pytest

from part_b.nodes import summary_generator as summary_module
from part_b.nodes import topic_analyzer as topic_module
from part_b.schemas import (
    DialogueTurn,
    InterviewMetaDocument,
    QaPairsDocument,
    ResumeProfileDocument,
    TopicGroup,
)
from services.analysis_service import AnalysisService
from services.interview_repo import InterviewRepository


def _sample_meta(interview_id: str = "demo") -> InterviewMetaDocument:
    return InterviewMetaDocument(
        interview_id=interview_id,
        title="Backend Interview",
        source_file_name="demo.mp4",
        input_type="video",
        target_position="Backend Engineer",
        direction="backend",
    )


def _sample_resume() -> ResumeProfileDocument:
    return ResumeProfileDocument(
        target_positions=["Backend Engineer"],
        tech_stack=["Java", "Spring Boot", "Redis", "MySQL"],
    )


def _sample_qa_pairs(interview_id: str = "demo") -> QaPairsDocument:
    return QaPairsDocument(
        interview_id=interview_id,
        topics=[
            TopicGroup(
                topic_id=1,
                main_question="介绍一下你最近做的订单系统。",
                question_text="介绍一下你最近做的订单系统。",
                question_turn_ids=["t1"],
                answer_text="我最近负责一个订单系统，核心技术是 Java、Spring Boot、Redis 和 MySQL。",
                answer_turn_ids=["t2"],
                followups=[
                    {
                        "question": "Redis 在里面怎么用的？",
                        "answer": "主要做热点缓存和分布式锁，也处理缓存失效和重试兜底。",
                        "question_turn_ids": ["t3"],
                        "answer_turn_ids": ["t4"],
                    }
                ],
                turn_ids=["t1", "t2", "t3", "t4"],
                topic_summary="介绍订单系统和 Redis 的使用方式。",
                topic_type="project",
                exchange_count=4,
                has_followup=True,
                exchanges=[
                    DialogueTurn(turn_id="t1", speaker_id="0", role="interviewer", text="介绍一下你最近做的订单系统。"),
                    DialogueTurn(turn_id="t2", speaker_id="1", role="candidate", text="我最近负责一个订单系统，核心技术是 Java、Spring Boot、Redis 和 MySQL。"),
                    DialogueTurn(turn_id="t3", speaker_id="0", role="interviewer", text="Redis 在里面怎么用的？"),
                    DialogueTurn(turn_id="t4", speaker_id="1", role="candidate", text="主要做热点缓存和分布式锁，也处理缓存失效和重试兜底。"),
                ],
            ),
        ],
    )


@pytest.fixture
def analysis_service(tmp_path: Path) -> AnalysisService:
    repository = InterviewRepository(output_root=tmp_path)
    return AnalysisService(repository=repository)


def test_rerun_from_b4_reaches_completed(
    analysis_service: AnalysisService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(topic_module, "safe_invoke_json_model", lambda *args, **kwargs: None)
    monkeypatch.setattr(summary_module, "safe_invoke_json_model", lambda *args, **kwargs: None)

    interview_id = analysis_service.create_interview_shell("demo.mp4", input_type="video")
    repository = analysis_service.repository

    meta = repository.load_meta(interview_id)
    assert meta is not None
    meta.target_position = "Backend Engineer"
    meta.direction = "backend"
    repository.save_meta(meta)

    analysis_service.profile_service.update_resume(_sample_resume())
    repository.save_qa_pairs(_sample_qa_pairs(interview_id=interview_id))

    final_status = analysis_service.rerun_from_stage(interview_id, "B4")
    bundle = repository.load_interview(interview_id)

    assert final_status.current_stage == "B6"
    assert final_status.status.value == "completed"
    assert bundle.analyses is not None
    assert bundle.report_markdown is not None
    assert bundle.capability_snapshot is not None


def test_export_bundle_payload_contains_saved_documents(
    analysis_service: AnalysisService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(topic_module, "safe_invoke_json_model", lambda *args, **kwargs: None)
    monkeypatch.setattr(summary_module, "safe_invoke_json_model", lambda *args, **kwargs: None)

    interview_id = analysis_service.create_interview_shell("demo.mp4", input_type="video")
    repository = analysis_service.repository

    meta = repository.load_meta(interview_id)
    assert meta is not None
    meta.target_position = "Backend Engineer"
    meta.direction = "backend"
    repository.save_meta(meta)

    analysis_service.profile_service.update_resume(_sample_resume())
    repository.save_qa_pairs(_sample_qa_pairs(interview_id=interview_id))
    analysis_service.run_phase4(interview_id)

    payload = analysis_service.export_bundle_payload(interview_id)

    assert payload["interview_id"] == interview_id
    assert payload["status"]["current_stage"] == "B6"
    assert payload["status"]["status"] == "completed"
    assert payload["analyses"] is not None
    assert payload["report_markdown"]
