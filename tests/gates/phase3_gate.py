from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from part_b.nodes import context_completer as context_module
from part_b.nodes import qa_pairer as qa_module
from part_b.nodes import role_identifier as role_module
from part_b.schemas import (
    InterviewMetaDocument,
    ResumeProfileDocument,
    TranscriptSegment,
    TranscriptionDocument,
)
from services.analysis_service import AnalysisService
from services.interview_repo import InterviewRepository


def run_phase3_gate() -> list[tuple[str, str, str]]:
    root = Path(__file__).resolve().parents[1] / "runtime" / "phase3"
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

    def sample_transcription() -> TranscriptionDocument:
        return TranscriptionDocument(
            interview_id="demo",
            segments=[
                TranscriptSegment(segment_id="1", speaker_id="1", text="Please introduce the order system you built recently."),
                TranscriptSegment(segment_id="2", speaker_id="0", text="I owned an order system built with Java and Spring Boot."),
                TranscriptSegment(segment_id="3", speaker_id="1", text="How did you use Redis in that project?"),
                TranscriptSegment(segment_id="4", speaker_id="0", text="We used Redis for hot cache and distributed locking, and handled invalidation carefully."),
                TranscriptSegment(segment_id="5", speaker_id="1", text="Why did you split services this way?"),
                TranscriptSegment(segment_id="6", speaker_id="0", text="We split order, inventory, and payment services to isolate complexity."),
                TranscriptSegment(segment_id="7", speaker_id="1", text="Why did you decide not to stay at your current company?"),
                TranscriptSegment(segment_id="8", speaker_id="0", text="The company mainly builds internal efficiency tools, which conflicts with my long-term direction."),
                TranscriptSegment(segment_id="9", speaker_id="1", text="When can you join?"),
                TranscriptSegment(segment_id="10", speaker_id="0", text="Mid March."),
            ],
        )

    def sample_meta() -> InterviewMetaDocument:
        return InterviewMetaDocument(
            interview_id="demo",
            title="demo",
            source_file_name="demo.mp3",
            input_type="audio",
        )

    def sample_resume() -> ResumeProfileDocument:
        return ResumeProfileDocument(
            target_positions=["Backend Engineer"],
            tech_stack=["Java", "Spring Boot", "Redis", "MySQL"],
        )

    def role_identification_heuristic() -> None:
        original = role_module.safe_invoke_json_model
        role_module.safe_invoke_json_model = lambda *args, **kwargs: None
        try:
            result, updated = role_module.identify_roles(sample_transcription())
        finally:
            role_module.safe_invoke_json_model = original

        role_map = {item.speaker_id: item.role.value for item in result.assignments}
        assert role_map["0"] == "candidate"
        assert role_map["1"] == "interviewer"
        assert updated.segments[0].role.value == "interviewer"
        assert updated.segments[1].role.value == "candidate"

    def context_completion_fallback() -> None:
        original = context_module.safe_invoke_json_model
        context_module.safe_invoke_json_model = lambda *args, **kwargs: None
        try:
            result, meta = context_module.complete_context(
                sample_transcription(),
                meta=sample_meta(),
                resume=sample_resume(),
            )
        finally:
            context_module.safe_invoke_json_model = original

        assert result.target_position == "Backend Engineer"
        assert meta.target_position == "Backend Engineer"
        assert meta.direction == "backend"

    def qa_pair_extraction_llm_primary() -> None:
        original_role = role_module.safe_invoke_json_model
        original_qa = qa_module.safe_invoke_json_model
        role_module.safe_invoke_json_model = lambda *args, **kwargs: None

        def fake_qa_call(*args, **kwargs):
            return qa_module.QaExtractionBatch(
                qa_pairs=[
                    qa_module.QaPairDraft(
                        qa_id=1,
                        question_turn_ids=["t1"],
                        answer_turn_ids=["t2"],
                        question="Please introduce the order system you built recently.",
                        answer="I owned an order system built with Java and Spring Boot.",
                        topic_type="project",
                    ),
                    qa_module.QaPairDraft(
                        qa_id=2,
                        question_turn_ids=["t3"],
                        answer_turn_ids=["t4"],
                        question="How did you use Redis in that project?",
                        answer="We used Redis for hot cache and distributed locking, and handled invalidation carefully.",
                        topic_type="technical",
                    ),
                    qa_module.QaPairDraft(
                        qa_id=3,
                        question_turn_ids=["t5"],
                        answer_turn_ids=["t6"],
                        question="Why did you split services this way?",
                        answer="We split order, inventory, and payment services to isolate complexity.",
                        topic_type="technical",
                    ),
                    qa_module.QaPairDraft(
                        qa_id=4,
                        question_turn_ids=["t7"],
                        answer_turn_ids=["t8"],
                        question="Why did you decide not to stay at your current company?",
                        answer="The company mainly builds internal efficiency tools, which conflicts with my long-term direction.",
                        topic_type="behavioral",
                    ),
                    qa_module.QaPairDraft(
                        qa_id=5,
                        question_turn_ids=["t9"],
                        answer_turn_ids=["t10"],
                        question="When can you join?",
                        answer="Mid March.",
                        topic_type="hr",
                    ),
                ]
            )

        qa_module.safe_invoke_json_model = fake_qa_call
        try:
            _, updated = role_module.identify_roles(sample_transcription())
            document = qa_module.build_qa_pairs(updated, meta=sample_meta())
        finally:
            role_module.safe_invoke_json_model = original_role
            qa_module.safe_invoke_json_model = original_qa

        assert len(document.topics) == 4
        assert document.topics[0].question_text.startswith("Please introduce the order system")
        assert document.topics[1].question_text.startswith("How did you use Redis")
        assert document.topics[2].question_text.startswith("Why did you split services")
        assert document.topics[3].question_text.startswith("Why did you decide not to stay")
        assert all("join" not in (topic.question_text or "").lower() for topic in document.topics)

    def qa_pair_extraction_fallback() -> None:
        original_role = role_module.safe_invoke_json_model
        original_qa = qa_module.safe_invoke_json_model
        role_module.safe_invoke_json_model = lambda *args, **kwargs: None
        qa_module.safe_invoke_json_model = lambda *args, **kwargs: None
        try:
            _, updated = role_module.identify_roles(sample_transcription())
            document = qa_module.build_qa_pairs(updated, meta=sample_meta())
        finally:
            role_module.safe_invoke_json_model = original_role
            qa_module.safe_invoke_json_model = original_qa

        assert len(document.topics) >= 3
        assert document.topics[0].question_text
        assert document.topics[0].answer_text is not None

    def analysis_service_phase3_flow() -> None:
        original_role = role_module.safe_invoke_json_model
        original_context = context_module.safe_invoke_json_model
        original_qa = qa_module.safe_invoke_json_model
        role_module.safe_invoke_json_model = lambda *args, **kwargs: None
        context_module.safe_invoke_json_model = lambda *args, **kwargs: None
        qa_module.safe_invoke_json_model = lambda *args, **kwargs: None
        try:
            repository = InterviewRepository(output_root=root / "repo")
            service = AnalysisService(repository=repository)
            interview_id = service.create_interview_shell("demo.mp3", input_type="audio")
            service.profile_service.update_resume(sample_resume())
            transcription = sample_transcription().model_copy(update={"interview_id": interview_id})
            repository.save_transcription(transcription)
            service.run_phase3(interview_id)
            bundle = repository.load_interview(interview_id)
        finally:
            role_module.safe_invoke_json_model = original_role
            context_module.safe_invoke_json_model = original_context
            qa_module.safe_invoke_json_model = original_qa

        assert bundle.status is not None
        assert bundle.status.stages["B1"].value == "success"
        assert bundle.status.stages["B2"].value == "success"
        assert bundle.status.stages["B3"].value == "success"
        assert bundle.qa_pairs is not None
        assert bundle.meta is not None
        assert bundle.meta.target_position == "Backend Engineer"
        assert bundle.qa_pairs.topics[0].question_text

    check("role_identification_heuristic", role_identification_heuristic)
    check("context_completion_fallback", context_completion_fallback)
    check("qa_pair_extraction_llm_primary", qa_pair_extraction_llm_primary)
    check("qa_pair_extraction_fallback", qa_pair_extraction_fallback)
    check("analysis_service_phase3_flow", analysis_service_phase3_flow)
    return results
