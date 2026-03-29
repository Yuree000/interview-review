from __future__ import annotations

from pathlib import Path

import pytest

from part_b.nodes import summary_generator as summary_module
from part_b.nodes import topic_analyzer as topic_module
from part_b.reporting import render_report_markdown
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
                answer_turn_ids=["t2", "t4"],
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
                    DialogueTurn(
                        turn_id="t1",
                        speaker_id="0",
                        role="interviewer",
                        text="介绍一下你最近做的订单系统。",
                        start_ms=0,
                        end_ms=2000,
                    ),
                    DialogueTurn(
                        turn_id="t2",
                        speaker_id="1",
                        role="candidate",
                        text="我最近负责一个订单系统，核心技术是 Java、Spring Boot、Redis 和 MySQL。",
                        start_ms=3000,
                        end_ms=8000,
                    ),
                    DialogueTurn(
                        turn_id="t3",
                        speaker_id="0",
                        role="interviewer",
                        text="Redis 在里面怎么用的？",
                        start_ms=9000,
                        end_ms=11000,
                    ),
                    DialogueTurn(
                        turn_id="t4",
                        speaker_id="1",
                        role="candidate",
                        text="主要做热点缓存和分布式锁，也处理缓存失效和重试兜底。",
                        start_ms=12000,
                        end_ms=17000,
                    ),
                ],
            ),
        ],
    )


def test_render_report_markdown_uses_phase4_expected_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(topic_module, "safe_invoke_json_model", lambda *args, **kwargs: None)
    monkeypatch.setattr(summary_module, "safe_invoke_json_model", lambda *args, **kwargs: None)

    analyses = topic_module.analyze_topics(
        _sample_qa_pairs(),
        meta=_sample_meta(),
        resume=_sample_resume(),
    )
    analyses.summary = summary_module.generate_interview_summary(
        analyses.analyses,
        meta=_sample_meta(),
        resume=_sample_resume(),
    )

    markdown = render_report_markdown(meta=_sample_meta(), analyses=analyses)

    assert "# 面试复盘报告" in markdown
    assert "## 总体结论" in markdown
    assert "## 逐题复盘" in markdown
    assert "必答点" in markdown
    assert "答题框架" in markdown
    assert "评分拆解" in markdown
    assert "综合加权" in markdown
    assert "00:03 - 00:08" in markdown


def test_run_phase4_marks_pipeline_completed_and_b6_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(topic_module, "safe_invoke_json_model", lambda *args, **kwargs: None)
    monkeypatch.setattr(summary_module, "safe_invoke_json_model", lambda *args, **kwargs: None)

    repository = InterviewRepository(output_root=tmp_path)
    service = AnalysisService(repository=repository)
    interview_id = service.create_interview_shell("demo.mp4", input_type="video")

    meta = repository.load_meta(interview_id)
    assert meta is not None
    meta.target_position = "Backend Engineer"
    meta.direction = "backend"
    repository.save_meta(meta)

    service.profile_service.update_resume(_sample_resume())
    repository.save_qa_pairs(_sample_qa_pairs(interview_id=interview_id))

    service.run_phase4(interview_id)
    bundle = repository.load_interview(interview_id)

    assert bundle.status is not None
    assert bundle.status.current_stage == "B6"
    assert bundle.status.status.value == "completed"
    assert bundle.status.stages["B5"].value == "success"
    assert bundle.status.stages["B6"].value == "success"
    assert bundle.analyses is not None
    assert bundle.analyses.analyses[0].evidence_items
