from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from part_b.schemas import (
    AnalysesDocument,
    InterviewMetaDocument,
    PipelineStatus,
    QaPairsDocument,
    ResumeProfileDocument,
    StageStatus,
    StatusDocument,
    TopicAnalysis,
    QuestionUnderstanding,
    RubricScore,
)
from services.analysis_service import AnalysisService
from services.interview_repo import InterviewRepository
from services.profile_service import ProfileService


def test_status_document_has_default_stages() -> None:
    document = StatusDocument(interview_id="demo")

    assert document.status == PipelineStatus.pending
    assert document.current_stage == "A1"
    assert document.stages["A1"] == StageStatus.pending
    assert document.stages["B6"] == StageStatus.pending


def test_repository_round_trip(tmp_path: Path) -> None:
    repository = InterviewRepository(output_root=tmp_path)
    interview_id = "2026-03-08_backend_java"

    repository.save_status(StatusDocument(interview_id=interview_id))
    repository.save_meta(
        InterviewMetaDocument(
            interview_id=interview_id,
            title="后端 Java 面试",
            source_file_name="demo.mp4",
            input_type="video",
        )
    )
    repository.save_qa_pairs(QaPairsDocument(interview_id=interview_id))
    repository.save_analyses(
        AnalysesDocument(
            interview_id=interview_id,
            analyses=[
                TopicAnalysis(
                    topic_id=1,
                    main_question="介绍一下微服务经验",
                    question_understanding=QuestionUnderstanding(
                        question_type="technical",
                        skill_tested=["microservice"],
                        expected_points=["service discovery"],
                    ),
                    rubric=RubricScore(
                        accuracy=8,
                        completeness=7,
                        depth=8,
                        structure=7,
                        position_fit=8,
                        reasoning="基础结构完整",
                    ),
                )
            ],
        )
    )

    bundle = repository.load_interview(interview_id)
    listing = repository.list_all()

    assert bundle.status is not None
    assert bundle.meta is not None
    assert bundle.meta.title == "后端 Java 面试"
    assert bundle.analyses is not None
    assert bundle.analyses.analyses[0].main_question == "介绍一下微服务经验"
    assert len(listing) == 1
    assert listing[0].interview_id == interview_id


def test_profile_service_round_trip(tmp_path: Path) -> None:
    service = ProfileService(output_root=tmp_path)
    service.update_resume(
        ResumeProfileDocument(
            name="张三",
            target_positions=["后端开发工程师"],
            tech_stack=["Java", "Spring Boot"],
        )
    )

    profile = service.get_resume()

    assert profile is not None
    assert profile.name == "张三"
    assert profile.tech_stack == ["Java", "Spring Boot"]


def test_schema_validation_failure() -> None:
    try:
        RubricScore(
            accuracy=11,
            completeness=7,
            depth=8,
            structure=7,
            position_fit=8,
        )
    except ValidationError:
        return
    raise AssertionError("RubricScore 应该在非法分值时抛出 ValidationError")


def test_analysis_service_resume_from_resets_following_stages(tmp_path: Path) -> None:
    repository = InterviewRepository(output_root=tmp_path)
    service = AnalysisService(repository=repository)
    interview_id = service.create_interview_shell("demo.mp4", input_type="video")

    status = repository.load_status(interview_id)
    assert status is not None

    status.stages["A1"] = StageStatus.success
    status.stages["A2"] = StageStatus.success
    status.stages["B1"] = StageStatus.failed
    repository.save_status(status)

    resumed = service.resume_from(interview_id, "B1")

    assert resumed.current_stage == "B1"
    assert resumed.stages["B1"] == StageStatus.pending
    assert resumed.stages["B6"] == StageStatus.pending
