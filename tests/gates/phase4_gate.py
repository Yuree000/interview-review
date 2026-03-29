from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from part_b.nodes import summary_generator as summary_module
from part_b.nodes import topic_analyzer as topic_module
from part_b.reporting import render_report_markdown
from part_b.schemas import (
    DialogueTurn,
    InterviewMetaDocument,
    QaPairsDocument,
    QuestionUnderstanding,
    ReferenceAnswer,
    ResumeProfileDocument,
    RubricScore,
    TopicGroup,
)
from services.analysis_service import AnalysisService
from services.interview_repo import InterviewRepository


def run_phase4_gate() -> list[tuple[str, str, str]]:
    root = Path(__file__).resolve().parents[1] / "runtime" / "phase4"
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

    def sample_meta(interview_id: str = "demo") -> InterviewMetaDocument:
        return InterviewMetaDocument(
            interview_id=interview_id,
            title="Backend Interview",
            source_file_name="demo.mp4",
            input_type="video",
            target_position="Backend Engineer",
            direction="backend",
        )

    def sample_resume() -> ResumeProfileDocument:
        return ResumeProfileDocument(
            target_positions=["Backend Engineer"],
            tech_stack=["Java", "Spring Boot", "Redis", "MySQL"],
        )

    def sample_qa_pairs(interview_id: str = "demo") -> QaPairsDocument:
        return QaPairsDocument(
            interview_id=interview_id,
            topics=[
                TopicGroup(
                    topic_id=1,
                    main_question="请介绍一下你最近做的订单系统。",
                    question_text="请介绍一下你最近做的订单系统。",
                    question_turn_ids=["t1"],
                    answer_text="我最近负责一个订单系统，核心技术是 Java、Spring Boot、Redis 和 MySQL。",
                    answer_turn_ids=["t2", "t4", "t6"],
                    followups=[
                        {
                            "question": "Redis 在里面怎么用的？",
                            "answer": "主要做热点缓存和分布式锁，也处理缓存失效和重试兜底。",
                            "question_turn_ids": ["t3"],
                            "answer_turn_ids": ["t4"],
                        },
                        {
                            "question": "服务为什么这样拆分？",
                            "answer": "我们按订单、库存、支付拆分，核心是隔离复杂度并提升扩展性，上线后接口延迟下降了 30%。",
                            "question_turn_ids": ["t5"],
                            "answer_turn_ids": ["t6"],
                        },
                    ],
                    turn_ids=["t1", "t2", "t3", "t4", "t5", "t6"],
                    topic_summary="介绍订单系统以及 Redis 和服务拆分思路。",
                    topic_type="project",
                    exchange_count=6,
                    has_followup=True,
                    exchanges=[
                        DialogueTurn(
                            turn_id="t1",
                            speaker_id="0",
                            role="interviewer",
                            text="请介绍一下你最近做的订单系统。",
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
                        DialogueTurn(
                            turn_id="t5",
                            speaker_id="0",
                            role="interviewer",
                            text="服务为什么这样拆分？",
                            start_ms=18000,
                            end_ms=20000,
                        ),
                        DialogueTurn(
                            turn_id="t6",
                            speaker_id="1",
                            role="candidate",
                            text="我们按订单、库存、支付拆分，核心是隔离复杂度并提升扩展性，上线后接口延迟下降了 30%。",
                            start_ms=21000,
                            end_ms=26000,
                        ),
                    ],
                ),
                TopicGroup(
                    topic_id=2,
                    main_question="你为什么想加入我们团队？",
                    question_text="你为什么想加入我们团队？",
                    question_turn_ids=["t7"],
                    answer_text="我希望继续做高并发后端，也认可你们的业务方向。",
                    answer_turn_ids=["t8"],
                    turn_ids=["t7", "t8"],
                    topic_summary="表达岗位匹配和成长方向。",
                    topic_type="behavioral",
                    exchange_count=2,
                    has_followup=False,
                    exchanges=[
                        DialogueTurn(
                            turn_id="t7",
                            speaker_id="0",
                            role="interviewer",
                            text="你为什么想加入我们团队？",
                            start_ms=30000,
                            end_ms=32000,
                        ),
                        DialogueTurn(
                            turn_id="t8",
                            speaker_id="1",
                            role="candidate",
                            text="我希望继续做高并发后端，也认可你们的业务方向。",
                            start_ms=33000,
                            end_ms=37000,
                        ),
                    ],
                ),
            ],
        )

    def topic_analysis_fallback() -> None:
        original = topic_module.safe_invoke_json_model
        topic_module.safe_invoke_json_model = lambda *args, **kwargs: None
        try:
            analysis = topic_module.analyze_topic(
                sample_qa_pairs().topics[0],
                meta=sample_meta(),
                resume=sample_resume(),
            )
        finally:
            topic_module.safe_invoke_json_model = original

        assert analysis.reference_answer is not None
        assert analysis.reference_answer.must_hit_points
        assert analysis.reference_answer.answer_framework
        assert analysis.question_understanding.skill_tested
        assert 1 <= analysis.rubric.accuracy <= 10
        assert analysis.evidence_quotes
        assert analysis.evidence_items
        assert analysis.evidence_items[0].start_ms == 3000
        assert analysis.evidence_items[0].end_ms == 8000

    def topic_analysis_llm_split_merge() -> None:
        original = topic_module.safe_invoke_json_model

        def fake_llm_call(response_model, *args, **kwargs):
            if response_model is ReferenceAnswer:
                return ReferenceAnswer(
                    reference_standard="先给核心结论，再补充 Redis 用法、拆分原因和结果指标。",
                    reference_personalized="结合你在 Java/Spring Boot 项目里的经历，把缓存、一致性和服务拆分串起来讲。",
                    must_hit_points=[],
                    answer_framework=[],
                    sources=[],
                )
            if response_model is topic_module.TopicEvaluationDraft:
                return topic_module.TopicEvaluationDraft(
                    question_understanding=QuestionUnderstanding(
                        question_type="project",
                        skill_tested=[],
                        expected_points=[],
                    ),
                    rubric=RubricScore(
                        accuracy=8,
                        completeness=8,
                        depth=7,
                        structure=7,
                        position_fit=8,
                        followup_handling=7,
                        reasoning="llm_evaluation",
                    ),
                    strengths=[],
                    weaknesses=["缺少更明确的量化结果。"],
                    evidence_quotes=[],
                )
            return None

        topic_module.safe_invoke_json_model = fake_llm_call
        try:
            analysis = topic_module.analyze_topic(
                sample_qa_pairs().topics[0],
                meta=sample_meta(),
                resume=sample_resume(),
            )
        finally:
            topic_module.safe_invoke_json_model = original

        assert analysis.reference_answer is not None
        assert analysis.reference_answer.reference_standard.startswith("先给核心结论")
        assert analysis.reference_answer.must_hit_points
        assert analysis.reference_answer.answer_framework
        assert analysis.question_understanding.skill_tested
        assert analysis.question_understanding.expected_points
        assert analysis.weaknesses == ["缺少更明确的量化结果。"]
        assert analysis.evidence_quotes
        assert analysis.evidence_items

    def summary_and_report_generation() -> None:
        original_topic = topic_module.safe_invoke_json_model
        original_summary = summary_module.safe_invoke_json_model
        topic_module.safe_invoke_json_model = lambda *args, **kwargs: None
        summary_module.safe_invoke_json_model = lambda *args, **kwargs: None
        try:
            analyses = topic_module.analyze_topics(
                sample_qa_pairs(),
                meta=sample_meta(),
                resume=sample_resume(),
            )
            analyses.summary = summary_module.generate_interview_summary(
                analyses.analyses,
                meta=sample_meta(),
                resume=sample_resume(),
            )
            markdown = render_report_markdown(meta=sample_meta(), analyses=analyses)
        finally:
            topic_module.safe_invoke_json_model = original_topic
            summary_module.safe_invoke_json_model = original_summary

        assert analyses.summary is not None
        assert "weighted_total" in analyses.summary.average_scores
        assert "# 面试复盘报告" in markdown
        assert "## 总体结论" in markdown
        assert "### 题目 1" in markdown
        assert "评分拆解" in markdown
        assert "综合加权" in markdown
        assert "证据时间线" in markdown
        assert "00:03 - 00:08" in markdown
        assert "必答点" in markdown
        assert "答题框架" in markdown

    def analysis_service_phase4_flow() -> None:
        original_topic = topic_module.safe_invoke_json_model
        original_summary = summary_module.safe_invoke_json_model
        topic_module.safe_invoke_json_model = lambda *args, **kwargs: None
        summary_module.safe_invoke_json_model = lambda *args, **kwargs: None
        try:
            repository = InterviewRepository(output_root=root / "repo")
            service = AnalysisService(repository=repository)
            interview_id = service.create_interview_shell("demo.mp4", input_type="video")
            meta = repository.load_meta(interview_id)
            assert meta is not None
            meta.target_position = "Backend Engineer"
            meta.direction = "backend"
            repository.save_meta(meta)
            service.profile_service.update_resume(sample_resume())
            qa_pairs = sample_qa_pairs(interview_id=interview_id)
            repository.save_qa_pairs(qa_pairs)
            service.run_phase4(interview_id)
            bundle = repository.load_interview(interview_id)
        finally:
            topic_module.safe_invoke_json_model = original_topic
            summary_module.safe_invoke_json_model = original_summary

        assert bundle.status is not None
        assert bundle.status.stages["B4"].value == "success"
        assert bundle.status.stages["B5"].value == "success"
        assert bundle.status.stages["B6"].value == "success"
        assert bundle.status.current_stage == "B6"
        assert bundle.status.status.value == "completed"
        assert bundle.analyses is not None
        assert bundle.analyses.summary is not None
        assert bundle.analyses.analyses[0].evidence_items
        assert bundle.report_markdown is not None
        assert "## 逐题复盘" in bundle.report_markdown
        assert "评分拆解" in bundle.report_markdown
        assert "综合加权" in bundle.report_markdown
        assert "证据时间线" in bundle.report_markdown
        assert "00:03 - 00:08" in bundle.report_markdown
        assert "必答点" in bundle.report_markdown

    check("topic_analysis_fallback", topic_analysis_fallback)
    check("topic_analysis_llm_split_merge", topic_analysis_llm_split_merge)
    check("summary_and_report_generation", summary_and_report_generation)
    check("analysis_service_phase4_flow", analysis_service_phase4_flow)
    return results
