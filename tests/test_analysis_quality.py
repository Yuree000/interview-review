from __future__ import annotations

import pytest

from part_b.nodes import summary_generator as summary_module
from part_b.nodes import topic_analyzer as topic_module
from part_b.reporting import render_report_markdown
from part_b.schemas import DialogueTurn, InterviewMetaDocument, ResumeProfileDocument, TopicGroup


def _sample_meta() -> InterviewMetaDocument:
    return InterviewMetaDocument(
        interview_id="demo",
        title="Backend Interview",
        source_file_name="demo.mp4",
        input_type="video",
        target_position="Backend Engineer",
        direction="backend",
    )


def _sample_resume() -> ResumeProfileDocument:
    return ResumeProfileDocument(
        target_positions=["Backend Engineer"],
        tech_stack=["Java", "Spring Boot", "Redis"],
    )


def _sample_topic() -> TopicGroup:
    return TopicGroup(
        topic_id=1,
        main_question="介绍一下你最近做的缓存设计。",
        question_text="介绍一下你最近做的缓存设计。",
        question_turn_ids=["q1"],
        answer_text="我负责订单缓存层，使用 Redis 作为热点缓存，并补充了失效和回源策略。",
        answer_turn_ids=["a1", "a2"],
        turn_ids=["q1", "a1", "a2"],
        topic_summary="订单缓存设计与一致性处理。",
        topic_type="technical",
        exchange_count=3,
        has_followup=False,
        exchanges=[
            DialogueTurn(
                turn_id="q1",
                speaker_id="0",
                role="interviewer",
                text="介绍一下你最近做的缓存设计。",
                start_ms=0,
                end_ms=2000,
            ),
            DialogueTurn(
                turn_id="a1",
                speaker_id="1",
                role="candidate",
                text="我负责订单缓存层，使用 Redis 作为热点缓存。",
                start_ms=3000,
                end_ms=8000,
            ),
            DialogueTurn(
                turn_id="a2",
                speaker_id="1",
                role="candidate",
                text="同时补充了失效和回源策略，避免脏数据和击穿。",
                start_ms=9000,
                end_ms=14000,
            ),
        ],
    )


def test_analyze_topic_builds_structured_evidence_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(topic_module, "safe_invoke_json_model", lambda *args, **kwargs: None)

    analysis = topic_module.analyze_topic(
        _sample_topic(),
        meta=_sample_meta(),
        resume=_sample_resume(),
    )

    assert analysis.evidence_items
    assert analysis.evidence_items[0].turn_id == "a1"
    assert analysis.evidence_items[0].start_ms == 3000
    assert analysis.evidence_items[0].end_ms == 8000
    assert analysis.evidence_quotes


def test_render_report_markdown_includes_score_breakdown_and_timed_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(topic_module, "safe_invoke_json_model", lambda *args, **kwargs: None)
    monkeypatch.setattr(summary_module, "safe_invoke_json_model", lambda *args, **kwargs: None)

    analyses = topic_module.analyze_topics(
        type("QaDoc", (), {"interview_id": "demo", "topics": [_sample_topic()]})(),
        meta=_sample_meta(),
        resume=_sample_resume(),
    )
    analyses.summary = summary_module.generate_interview_summary(
        analyses.analyses,
        meta=_sample_meta(),
        resume=_sample_resume(),
    )

    markdown = render_report_markdown(meta=_sample_meta(), analyses=analyses)

    assert "评分拆解" in markdown
    assert "综合加权" in markdown
    assert "00:03 - 00:08" in markdown
