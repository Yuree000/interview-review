from __future__ import annotations

from pathlib import Path

from part_b.schemas import (
    AnalysesDocument,
    CapabilitySnapshotDocument,
    InterviewMetaDocument,
    InterviewSummary,
    QuestionUnderstanding,
    RubricScore,
    TopicAnalysis,
)
from services.compare_service import CompareService
from services.interview_repo import InterviewRepository


def _sample_analysis(
    interview_id: str,
    *,
    question: str,
    weighted_reasoning: str,
    strengths: list[str],
    weaknesses: list[str],
    weighted_total: float,
) -> AnalysesDocument:
    return AnalysesDocument(
        interview_id=interview_id,
        analyses=[
            TopicAnalysis(
                topic_id=1,
                main_question=question,
                question_understanding=QuestionUnderstanding(
                    question_type="technical",
                    skill_tested=["system design"],
                    expected_points=["tradeoff", "result"],
                ),
                rubric=RubricScore(
                    accuracy=8,
                    completeness=7,
                    depth=8,
                    structure=7,
                    position_fit=8,
                    reasoning=weighted_reasoning,
                ),
                strengths=strengths,
                weaknesses=weaknesses,
            )
        ],
        summary=InterviewSummary(
            overall_summary="compare summary",
            strengths=strengths,
            weaknesses=weaknesses,
            confidence_notes=["fixture"],
            action_plan_7d=["practice"],
            average_scores={"weighted_total": weighted_total},
        ),
    )


def _build_service(tmp_path: Path) -> CompareService:
    repository = InterviewRepository(output_root=tmp_path)
    id_a = "2026-03-08_backend_a"
    id_b = "2026-03-08_backend_b"

    repository.save_meta(
        InterviewMetaDocument(
            interview_id=id_a,
            title="Interview A",
            source_file_name="a.mp4",
            input_type="video",
            target_position="Backend Engineer",
        )
    )
    repository.save_meta(
        InterviewMetaDocument(
            interview_id=id_b,
            title="Interview B",
            source_file_name="b.mp4",
            input_type="video",
            target_position="Backend Engineer",
        )
    )

    repository.save_analyses(
        _sample_analysis(
            id_a,
            question="How would you design a cache layer?",
            weighted_reasoning="before",
            strengths=["clear structure"],
            weaknesses=["needs more metrics"],
            weighted_total=7.1,
        )
    )
    repository.save_analyses(
        _sample_analysis(
            id_b,
            question="How would you design a cache layer？！",
            weighted_reasoning="after",
            strengths=["clear structure", "better tradeoff explanation"],
            weaknesses=["needs more examples"],
            weighted_total=8.0,
        )
    )

    repository.save_capability_snapshot(
        CapabilitySnapshotDocument(
            interview_id=id_a,
            public_dimensions={"communication": 7.0, "problem_solving": 7.2},
            role_dimensions={"technical": 7.1},
            strengths=["clear structure"],
            weaknesses=["needs more metrics"],
            next_focus=["quantify outcomes"],
            summary="snapshot a",
        )
    )
    repository.save_capability_snapshot(
        CapabilitySnapshotDocument(
            interview_id=id_b,
            public_dimensions={"communication": 8.1, "problem_solving": 6.6},
            role_dimensions={"technical": 7.8},
            strengths=["clear structure", "better tradeoff explanation"],
            weaknesses=["needs more examples"],
            next_focus=["add more project examples"],
            summary="snapshot b",
        )
    )

    return CompareService(repository=repository)


def test_compare_matches_topics_after_question_normalization(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    payload = service.compare("2026-03-08_backend_a", "2026-03-08_backend_b")

    assert len(payload.topic_deltas) == 1
    assert payload.topic_deltas[0].topic_key == "How would you design a cache layer?"
    assert payload.highlights.shared_topic_count == 1


def test_compare_payload_includes_highlights_and_export_data(tmp_path: Path) -> None:
    service = _build_service(tmp_path)

    payload = service.compare("2026-03-08_backend_a", "2026-03-08_backend_b")
    export_payload = service.export_payload(payload)

    assert payload.highlights.weighted_total_delta == 0.9
    assert payload.highlights.best_improved_dimension == "communication"
    assert payload.highlights.biggest_regression_dimension == "problem_solving"
    assert export_payload["highlights"]["weighted_total_delta"] == 0.9
    assert export_payload["summary_markdown"].startswith("# 面试对比")
