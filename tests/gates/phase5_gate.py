from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from part_b.schemas import (
    AnalysesDocument,
    InterviewMetaDocument,
    InterviewSummary,
    PipelineStatus,
    QaPairsDocument,
    QuestionUnderstanding,
    ReferenceAnswer,
    ReferenceSource,
    RubricScore,
    StageStatus,
    StatusDocument,
    TopicAnalysis,
)
from tests.gates.module_loader import load_module


InterviewRepository = load_module("gate_phase5_interview_repo", "services/interview_repo.py").InterviewRepository


def run_phase5_gate() -> list[tuple[str, str, str]]:
    root = Path(__file__).resolve().parents[1] / "runtime" / "phase5"
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

    def make_repo() -> tuple[InterviewRepository, str]:
        repo = InterviewRepository(output_root=root / "repo")
        interview_id = "2026-03-08_backend_demo"
        repo.save_meta(
            InterviewMetaDocument(
                interview_id=interview_id,
                title="Backend Demo Interview",
                source_file_name="demo.mp4",
                input_type="video",
                target_position="Backend Engineer",
                direction="backend",
            )
        )

        status = StatusDocument(
            interview_id=interview_id,
            status=PipelineStatus.analyzing,
            current_stage="B5",
        )
        status.stages["A1"] = StageStatus.success
        status.stages["A2"] = StageStatus.success
        status.stages["B1"] = StageStatus.success
        status.stages["B2"] = StageStatus.success
        status.stages["B3"] = StageStatus.success
        status.stages["B4"] = StageStatus.success
        status.stages["B5"] = StageStatus.success
        repo.save_status(status)

        repo.save_qa_pairs(QaPairsDocument(interview_id=interview_id))
        repo.save_analyses(
            AnalysesDocument(
                interview_id=interview_id,
                analyses=[
                    TopicAnalysis(
                        topic_id=1,
                        main_question="Describe your backend project",
                        question_understanding=QuestionUnderstanding(
                            question_type="project",
                            skill_tested=["backend engineering"],
                            expected_points=["scope", "ownership", "result"],
                        ),
                        rubric=RubricScore(
                            accuracy=8,
                            completeness=7,
                            depth=8,
                            structure=7,
                            position_fit=8,
                            reasoning="offline phase5 sample",
                        ),
                        strengths=["clear ownership"],
                        weaknesses=["could add more metrics"],
                        evidence_quotes=["I owned the order service."],
                        reference_answer=ReferenceAnswer(
                            reference_standard="State scope, ownership, decisions, and result.",
                            reference_personalized="Emphasize Java, Spring Boot, Redis, and outcome metrics.",
                            sources=[
                                ReferenceSource(
                                    title="Local interview heuristics",
                                    source_type="knowledge_base",
                                )
                            ],
                        ),
                    )
                ],
                summary=InterviewSummary(
                    overall_summary="Solid backend sample for PH5 gate.",
                    strengths=["clear ownership"],
                    weaknesses=["could add more metrics"],
                    confidence_notes=["offline fixture"],
                    action_plan_7d=["Add metrics to project answers."],
                    average_scores={"weighted_total": 7.6},
                ),
            )
        )
        repo.save_report(
            interview_id,
            "# Interview Report\n\n## Summary\n\nSolid backend sample.\n",
        )
        return repo, interview_id

    def repository_backed_history_listing() -> None:
        repo, interview_id = make_repo()
        items = repo.list_all()
        assert len(items) == 1
        assert items[0].interview_id == interview_id
        assert items[0].current_stage == "B5"
        assert items[0].title == "Backend Demo Interview"

    def bundle_contains_report_outputs() -> None:
        repo, interview_id = make_repo()
        bundle = repo.load_interview(interview_id)
        assert bundle.meta is not None
        assert bundle.analyses is not None
        assert bundle.report_markdown is not None
        assert bundle.report_markdown.startswith("# Interview Report")

    def report_file_persisted() -> None:
        repo, interview_id = make_repo()
        report_path = repo.get_interview_dir(interview_id) / repo.REPORT_FILE
        analyses_path = repo.get_interview_dir(interview_id) / repo.ANALYSES_FILE
        assert report_path.exists()
        assert analyses_path.exists()

    check("repository_backed_history_listing", repository_backed_history_listing)
    check("bundle_contains_report_outputs", bundle_contains_report_outputs)
    check("report_file_persisted", report_file_persisted)
    return results
