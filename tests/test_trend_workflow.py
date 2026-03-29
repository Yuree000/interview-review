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
from services.interview_repo import InterviewRepository
from services.trend_service import TrendService


def _sample_analysis(
    interview_id: str,
    *,
    weighted_total: float,
    weaknesses: list[str],
) -> AnalysesDocument:
    return AnalysesDocument(
        interview_id=interview_id,
        analyses=[
            TopicAnalysis(
                topic_id=1,
                main_question="Explain a backend project",
                question_understanding=QuestionUnderstanding(
                    question_type="technical",
                    skill_tested=["backend"],
                    expected_points=["tradeoff", "result"],
                ),
                rubric=RubricScore(
                    accuracy=8,
                    completeness=7,
                    depth=8,
                    structure=7,
                    position_fit=8,
                    reasoning=f"weighted_total={weighted_total}",
                ),
                strengths=["clear structure"],
                weaknesses=weaknesses,
            )
        ],
        summary=InterviewSummary(
            overall_summary="trend fixture",
            strengths=["clear structure"],
            weaknesses=weaknesses,
            confidence_notes=["fixture"],
            action_plan_7d=["practice"],
            average_scores={"weighted_total": weighted_total},
        ),
    )


def _seed_repo(tmp_path: Path) -> InterviewRepository:
    repo = InterviewRepository(output_root=tmp_path)
    fixtures = [
        (
            "2026-03-01_backend_a",
            "Interview A",
            "2026-03-01T10:00:00+08:00",
            7.0,
            {"communication": 6.8, "problem_solving": 6.9},
            ["needs more metrics", "answer is short"],
        ),
        (
            "2026-03-08_backend_b",
            "Interview B",
            "2026-03-08T10:00:00+08:00",
            7.8,
            {"communication": 7.5, "problem_solving": 7.1},
            ["needs more metrics"],
        ),
        (
            "2026-03-15_backend_c",
            "Interview C",
            "2026-03-15T10:00:00+08:00",
            8.2,
            {"communication": 8.0, "problem_solving": 7.8},
            ["needs more examples", "needs more metrics"],
        ),
    ]

    for interview_id, title, updated_at, weighted_total, dimensions, weaknesses in fixtures:
        repo.save_meta(
            InterviewMetaDocument(
                interview_id=interview_id,
                title=title,
                source_file_name=f"{interview_id}.mp4",
                input_type="video",
                target_position="Backend Engineer",
            )
        )
        repo.save_analyses(_sample_analysis(interview_id, weighted_total=weighted_total, weaknesses=weaknesses))
        repo.save_capability_snapshot(
            CapabilitySnapshotDocument(
                interview_id=interview_id,
                public_dimensions=dimensions,
                role_dimensions={"technical": weighted_total},
                strengths=["clear structure"],
                weaknesses=weaknesses,
                next_focus=["quantify outcomes"],
                summary=f"{title} snapshot",
                updated_at=updated_at,
            )
        )

    return repo


def test_trend_service_builds_sorted_timeline_and_highlights(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    service = TrendService(repository=repo)

    payload = service.build_payload()

    assert [point.interview_id for point in payload.points] == [
        "2026-03-01_backend_a",
        "2026-03-08_backend_b",
        "2026-03-15_backend_c",
    ]
    assert payload.highlights.run_count == 3
    assert payload.highlights.overall_delta == 1.2
    assert payload.highlights.best_improved_dimension == "communication"
    assert payload.highlights.biggest_regression_dimension is None
    assert payload.dimension_delta["overall"] == 1.2
    assert payload.dimension_delta["communication"] == 1.2


def test_trend_service_exports_recent_repeated_weaknesses(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path)
    service = TrendService(repository=repo)

    payload = service.build_payload()
    export_payload = service.export_payload(payload)

    assert payload.recent_repeated_weaknesses[0] == "needs more metrics"
    assert export_payload["highlights"]["run_count"] == 3
    assert export_payload["recent_repeated_weaknesses"][0] == "needs more metrics"
    assert export_payload["summary_markdown"].startswith("# 面试趋势")


def test_trend_service_backfills_missing_snapshot_from_analyses(tmp_path: Path) -> None:
    repo = InterviewRepository(output_root=tmp_path)
    interview_id = "2026-03-22_backend_d"
    repo.save_meta(
        InterviewMetaDocument(
            interview_id=interview_id,
            title="Interview D",
            source_file_name="d.mp4",
            input_type="video",
            target_position="Backend Engineer",
        )
    )
    repo.save_analyses(
        _sample_analysis(
            interview_id,
            weighted_total=7.6,
            weaknesses=["needs more metrics"],
        )
    )

    service = TrendService(repository=repo)
    payload = service.build_payload()

    assert payload.points[0].interview_id == interview_id
    assert payload.points[0].overall == 7.6
    assert repo.load_capability_snapshot(interview_id) is not None
