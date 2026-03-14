from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from pydantic import ValidationError

from part_b.schemas import (
    AnalysesDocument,
    InterviewMetaDocument,
    PipelineStatus,
    QaPairsDocument,
    QuestionUnderstanding,
    ResumeProfileDocument,
    RubricScore,
    StageStatus,
    StatusDocument,
    TopicAnalysis,
)
from services.analysis_service import AnalysisService
from services.interview_repo import InterviewRepository
from services.profile_service import ProfileService


def run_phase1_gate() -> list[tuple[str, str, str]]:
    root = Path(__file__).resolve().parents[1] / "runtime" / "phase1"
    if root.exists():
        rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    results: list[tuple[str, str, str]] = []

    def check(name: str, fn) -> None:
        try:
            fn()
        except Exception as exc:  # pragma: no cover
            results.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))
        else:
            results.append((name, "PASS", "ok"))

    def schema_success() -> None:
        document = StatusDocument(interview_id="demo")
        assert document.status == PipelineStatus.pending
        assert document.stages["A1"] == StageStatus.pending

    def schema_failure() -> None:
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
        raise AssertionError("RubricScore should reject invalid scores")

    def repository_crud() -> None:
        repo_root = root / "repo"
        repository = InterviewRepository(output_root=repo_root)
        interview_id = "2026-03-08_backend_java"

        repository.save_status(StatusDocument(interview_id=interview_id))
        repository.save_meta(
            InterviewMetaDocument(
                interview_id=interview_id,
                title="Backend Java Interview",
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
                        main_question="Describe your microservice experience",
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
                            reasoning="Base structure is complete",
                        ),
                    )
                ],
            )
        )
        repository.save_report(interview_id, "# report")

        bundle = repository.load_interview(interview_id)
        assert bundle.meta is not None
        assert bundle.analyses is not None
        assert bundle.report_markdown is not None
        assert len(repository.list_all()) == 1

        repository.delete(interview_id)
        assert len(repository.list_all()) == 0

    def profile_service_round_trip() -> None:
        service = ProfileService(output_root=root / "profile")
        service.update_resume(
            ResumeProfileDocument(
                name="Zhang San",
                target_positions=["Backend Engineer"],
                tech_stack=["Java", "Spring Boot"],
            )
        )
        profile = service.get_resume()
        assert profile is not None
        assert profile.name == "Zhang San"

    def status_resume_flow() -> None:
        repository = InterviewRepository(output_root=root / "analysis")
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

    check("schema_success", schema_success)
    check("schema_failure", schema_failure)
    check("repository_crud", repository_crud)
    check("profile_service_round_trip", profile_service_round_trip)
    check("status_resume_flow", status_resume_flow)

    return results

