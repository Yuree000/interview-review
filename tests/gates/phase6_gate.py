from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from part_b.schemas import (
    AnalysesDocument,
    CapabilitySnapshotDocument,
    CompareResultDocument,
    GlobalProfileDocument,
    InterviewMetaDocument,
    InterviewSummary,
    QuestionUnderstanding,
    ResumeProfileDocument,
    RubricScore,
    TopicAnalysis,
)
from tests.gates.module_loader import load_module


InterviewRepository = load_module("gate_phase6_interview_repo", "services/interview_repo.py").InterviewRepository
ProfileService = load_module("gate_phase6_profile_service", "services/profile_service.py").ProfileService
ResumeIngestService = load_module("gate_phase6_resume_ingest_service", "services/resume_ingest_service.py").ResumeIngestService
CompareService = load_module("gate_phase6_compare_service", "services/compare_service.py").CompareService
TrendService = load_module("gate_phase6_trend_service", "services/trend_service.py").TrendService


def run_phase6_gate() -> list[tuple[str, str, str]]:
    root = Path(__file__).resolve().parents[1] / "runtime" / "phase6"
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

    def sample_analysis(interview_id: str, weighted_total: float) -> AnalysesDocument:
        return AnalysesDocument(
            interview_id=interview_id,
            analyses=[
                TopicAnalysis(
                    topic_id=1,
                    main_question="Explain your system design choices",
                    question_understanding=QuestionUnderstanding(
                        question_type="technical",
                        skill_tested=["system design"],
                        expected_points=["tradeoff", "scalability"],
                    ),
                    rubric=RubricScore(
                        accuracy=8,
                        completeness=7,
                        depth=8,
                        structure=7,
                        position_fit=8,
                        reasoning=f"weighted_total={weighted_total}",
                    ),
                    strengths=["good tradeoff explanation"],
                    weaknesses=["could quantify impact"],
                )
            ],
            summary=InterviewSummary(
                overall_summary="PH6 offline summary",
                strengths=["good tradeoff explanation"],
                weaknesses=["could quantify impact"],
                confidence_notes=["offline fixture"],
                action_plan_7d=["Practice quantified outcomes."],
                average_scores={"weighted_total": weighted_total},
            ),
        )

    def make_repo() -> tuple[InterviewRepository, str, str]:
        repo = InterviewRepository(output_root=root / "repo")
        id_a = "2026-03-08_backend_a"
        id_b = "2026-03-08_backend_b"
        repo.save_meta(
            InterviewMetaDocument(
                interview_id=id_a,
                title="Interview A",
                source_file_name="a.mp4",
                input_type="video",
                target_position="Backend Engineer",
            )
        )
        repo.save_meta(
            InterviewMetaDocument(
                interview_id=id_b,
                title="Interview B",
                source_file_name="b.mp4",
                input_type="video",
                target_position="Backend Engineer",
            )
        )
        repo.save_analyses(sample_analysis(id_a, 7.4))
        repo.save_analyses(sample_analysis(id_b, 8.1))
        repo.save_capability_snapshot(
            CapabilitySnapshotDocument(
                interview_id=id_a,
                public_dimensions={"communication": 7.2},
                role_dimensions={"backend": 7.5},
                strengths=["good tradeoff explanation"],
                weaknesses=["could quantify impact"],
                next_focus=["add metrics"],
                summary="snapshot a",
                updated_at="2026-03-08T10:00:00+08:00",
            )
        )
        repo.save_capability_snapshot(
            CapabilitySnapshotDocument(
                interview_id=id_b,
                public_dimensions={"communication": 8.1},
                role_dimensions={"backend": 8.0},
                strengths=["clear structure"],
                weaknesses=["needs deeper examples"],
                next_focus=["deeper examples"],
                summary="snapshot b",
                updated_at="2026-03-15T10:00:00+08:00",
            )
        )
        return repo, id_a, id_b

    def resume_and_global_profile_roundtrip() -> None:
        service = ProfileService(output_root=root / "profiles")
        service.update_resume(
            ResumeProfileDocument(
                name="Alex",
                target_positions=["Backend Engineer"],
                tech_stack=["Java", "Spring Boot", "Redis"],
            )
        )
        service.update_global_profile(
            GlobalProfileDocument(
                public_dimensions={"communication": 7.8},
                role_dimensions={"backend": {"architecture": 8.0}},
                strengths=["clear structure"],
                weaknesses=["needs more metrics"],
                learning_roadmap=["practice quantified results"],
                trend_summary="improving",
            )
        )
        resume = service.get_resume()
        global_profile = service.get_global_profile()
        assert resume is not None
        assert global_profile is not None
        assert resume.name == "Alex"
        assert global_profile.trend_summary == "improving"

    def comparison_input_bundle_available() -> None:
        repo, id_a, id_b = make_repo()
        analyses_a = repo.load_analyses(id_a)
        analyses_b = repo.load_analyses(id_b)
        snapshot_a = repo.load_capability_snapshot(id_a)
        snapshot_b = repo.load_capability_snapshot(id_b)
        assert analyses_a is not None
        assert analyses_b is not None
        assert analyses_a.summary is not None
        assert snapshot_a is not None
        assert snapshot_b is not None

    def compare_result_document_schema() -> None:
        document = CompareResultDocument(
            interview_id_a="a",
            interview_id_b="b",
            improvements=["depth improved"],
            regressions=["none"],
            repeated_issues=["metrics missing"],
            next_focus=["quantify outcomes"],
        )
        assert document.next_focus == ["quantify outcomes"]

    def compare_service_export_payload() -> None:
        repo, id_a, id_b = make_repo()
        service = CompareService(repository=repo)
        payload = service.compare(id_a, id_b)
        export_payload = service.export_payload(payload)
        assert "highlights" in export_payload
        assert export_payload["summary_markdown"].startswith("# 面试对比")

    def trend_service_export_payload() -> None:
        repo, _, _ = make_repo()
        service = TrendService(repository=repo)
        payload = service.build_payload()
        export_payload = service.export_payload(payload)
        assert payload.highlights.run_count == 2
        assert export_payload["points"][0]["interview_id"] == "2026-03-08_backend_a"
        assert export_payload["summary_markdown"].startswith("# 面试趋势")

    def resume_upload_ingest_roundtrip() -> None:
        service = ResumeIngestService(profile_service=ProfileService(output_root=root / "upload_profiles"))
        result = service.ingest_bytes(
            "resume.txt",
            "张三\nBackend Engineer\n5 years\nJava\nRedis\n项目经历\n订单系统\n负责接口设计".encode("utf-8"),
        )
        stored = service.profile_service.get_resume()
        assert stored is not None
        assert result.source_path == "resume.txt"
        assert "Backend Engineer" in stored.target_positions
        assert "Java" in stored.tech_stack
        assert stored.raw_text is not None

    check("resume_and_global_profile_roundtrip", resume_and_global_profile_roundtrip)
    check("comparison_input_bundle_available", comparison_input_bundle_available)
    check("compare_result_document_schema", compare_result_document_schema)
    check("compare_service_export_payload", compare_service_export_payload)
    check("trend_service_export_payload", trend_service_export_payload)
    check("resume_upload_ingest_roundtrip", resume_upload_ingest_roundtrip)
    return results
