from __future__ import annotations

import streamlit as st

from core.time_utils import format_ms_range, format_timestamp_ms
from part_b.schemas import FollowupPair, TopicAnalysis, TopicGroup, TranscriptionDocument
from services.interview_repo import InterviewBundle
from ui.theme import render_stat_cards


def render_analysis_bundle(bundle: InterviewBundle) -> None:
    transcript_count = len(bundle.transcription.segments) if bundle.transcription else 0
    qa_count = len(bundle.qa_pairs.topics) if bundle.qa_pairs else 0
    report_status = "Ready" if bundle.report_markdown else "Pending"
    pipeline_stage = bundle.status.current_stage if bundle.status else "Pending"
    pipeline_status = bundle.status.status.value if bundle.status else "pending"
    snapshot_status = "Ready" if bundle.capability_snapshot else "Pending"
    render_stat_cards(
        [
            ("Pipeline", f"{pipeline_stage} · {pipeline_status}", "Current pipeline stage and saved status"),
            ("Transcript Segments", str(transcript_count), "Speaker-attributed transcript blocks"),
            ("Review Questions", str(qa_count), "High-value questions selected for replay"),
            ("Report", report_status, "Final interview review markdown"),
            ("Snapshot", snapshot_status, "Capability snapshot generated from the saved run"),
        ]
    )
    st.write("")

    transcript_tab, qa_tab, report_tab = st.tabs(["Transcript", "QA Review", "Report"])

    with transcript_tab:
        render_transcript_text(bundle.transcription)

    with qa_tab:
        render_qa_pairs_with_reference(bundle)

    with report_tab:
        render_report(bundle.report_markdown)


def render_transcript_text(document: TranscriptionDocument | None) -> None:
    if document is None or not document.segments:
        st.info("No transcript is available yet. Run preprocessing first.")
        return

    transcript_text = "\n\n".join(
        _format_transcript_line(
            speaker_id=segment.speaker_id,
            role=segment.role.value,
            text=segment.text,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
        )
        for segment in document.segments
        if segment.text.strip()
    )

    with st.container(border=True):
        st.caption(f"{len(document.segments)} transcript segments, ready to copy")
        st.text_area(
            "transcript_text",
            value=transcript_text,
            height=620,
            disabled=True,
            label_visibility="collapsed",
        )


def render_qa_pairs_with_reference(bundle: InterviewBundle) -> None:
    if bundle.qa_pairs is None or not bundle.qa_pairs.topics:
        st.info("No QA pairs are available yet. Run phase 3 first.")
        return

    analysis_map = {
        analysis.topic_id: analysis
        for analysis in (bundle.analyses.analyses if bundle.analyses else [])
    }

    st.caption(f"{len(bundle.qa_pairs.topics)} review-worthy questions extracted from the interview")
    for index, topic in enumerate(bundle.qa_pairs.topics, start=1):
        analysis = analysis_map.get(topic.topic_id)
        title = topic.question_text or topic.main_question or f"Question {index}"
        with st.expander(f"Q{index}. {title}", expanded=index == 1):
            left, right = st.columns([1.05, 0.95])
            with left:
                _render_question_block(topic)
                st.write("")
                _render_answer_block(topic)
                st.write("")
                _render_followups_block(topic)
            with right:
                _render_analysis_insights_block(analysis)
                st.write("")
                _render_reference_block(analysis)


def render_report(report_markdown: str | None) -> None:
    if not report_markdown:
        st.info("The review report is not available yet. Run the full analysis flow first.")
        return
    with st.container(border=True):
        st.markdown(report_markdown)


def _render_question_block(topic: TopicGroup) -> None:
    with st.container(border=True):
        st.markdown("##### Main question")
        st.write(topic.question_text or topic.main_question or "No main question detected.")
        st.caption(f"Topic type: {topic.topic_type} | Exchanges: {topic.exchange_count}")
        if topic.topic_summary:
            st.caption(topic.topic_summary)


def _render_answer_block(topic: TopicGroup) -> None:
    with st.container(border=True):
        st.markdown("##### Candidate answer")
        answer_text = _candidate_answer(topic)
        if answer_text:
            st.write(answer_text)
        else:
            st.info("No candidate answer was confidently attached to this question.")


def _render_followups_block(topic: TopicGroup) -> None:
    followups = _followup_pairs(topic)
    if not followups:
        return

    with st.container(border=True):
        st.markdown("##### Follow-up exchange")
        for index, followup in enumerate(followups, start=1):
            question_text = followup.question.strip() or "Follow-up question"
            st.markdown(f"**{index}. Follow-up**")
            st.write(question_text)
            if followup.answer and followup.answer.strip():
                st.caption("Candidate response")
                st.write(followup.answer.strip())
            else:
                st.caption("Candidate response not detected.")


def _render_reference_block(analysis: TopicAnalysis | None) -> None:
    with st.container(border=True):
        st.markdown("##### AI reference answer")
        if analysis is None or analysis.reference_answer is None:
            st.info("Reference answer is not available yet.")
            return

        reference = analysis.reference_answer
        if reference.must_hit_points:
            st.markdown("**Must-hit points**")
            for point in reference.must_hit_points:
                st.write(f"- {point}")

        st.markdown("**Reference answer**")
        st.write(reference.reference_standard)

        if reference.reference_personalized:
            st.markdown("**Personalized variant**")
            st.write(reference.reference_personalized)

        if reference.answer_framework:
            st.markdown("**Answer framework**")
            for step in reference.answer_framework:
                st.write(f"- {step}")


def _render_analysis_insights_block(analysis: TopicAnalysis | None) -> None:
    with st.container(border=True):
        st.markdown("##### Analysis transparency")
        if analysis is None:
            st.info("Per-question analysis is not available yet.")
            return

        st.caption(f"Weighted total: {analysis.rubric.weighted_total()}")
        st.dataframe(
            [
                {"metric": label, "score": score}
                for label, score in _score_breakdown_rows(analysis)
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("**Evidence timeline**")
        evidence_lines = _evidence_lines(analysis)
        if evidence_lines:
            for line in evidence_lines:
                st.write(f"- {line}")
        else:
            st.info("No evidence snippets were attached to this topic.")


def _format_transcript_line(
    *,
    speaker_id: str,
    role: str,
    text: str,
    start_ms: int | None,
    end_ms: int | None,
) -> str:
    speaker = _speaker_label(speaker_id=speaker_id, role=role)
    if start_ms is None and end_ms is None:
        return f"{speaker}: {text}"
    return f"[{_format_range(start_ms, end_ms)}] {speaker}: {text}"


def _candidate_answer(topic: TopicGroup) -> str:
    if topic.answer_text and topic.answer_text.strip():
        return topic.answer_text.strip()
    answers = [
        turn.text.strip()
        for turn in topic.exchanges
        if turn.role.value == "candidate" and turn.text.strip()
    ]
    return "\n\n".join(answers)


def _followup_pairs(topic: TopicGroup) -> list[FollowupPair]:
    if topic.followups:
        return topic.followups

    if len(topic.exchanges) <= 2:
        return []

    pairs: list[FollowupPair] = []
    turns = topic.exchanges[2:]
    index = 0
    while index < len(turns):
        question_turns = []
        while index < len(turns) and turns[index].role.value == "interviewer":
            question_turns.append(turns[index])
            index += 1

        answer_turns = []
        while index < len(turns) and turns[index].role.value != "interviewer":
            answer_turns.append(turns[index])
            index += 1

        if question_turns or answer_turns:
            pairs.append(
                FollowupPair(
                    question="\n".join(turn.text.strip() for turn in question_turns if turn.text.strip()) or "Follow-up",
                    answer="\n".join(turn.text.strip() for turn in answer_turns if turn.text.strip()) or None,
                )
            )
    return pairs


def _speaker_label(*, speaker_id: str, role: str) -> str:
    if role == "candidate":
        return "Candidate"
    if role == "interviewer":
        return "Interviewer"
    return speaker_id or "Unknown speaker"


def _format_range(start_ms: int | None, end_ms: int | None) -> str:
    return format_ms_range(start_ms, end_ms)


def _format_timestamp(value_ms: int | None) -> str:
    return format_timestamp_ms(value_ms)


def _score_breakdown_rows(analysis: TopicAnalysis) -> list[tuple[str, str]]:
    label_map = {
        "accuracy": "Accuracy",
        "completeness": "Completeness",
        "depth": "Depth",
        "structure": "Structure",
        "position_fit": "Position Fit",
        "followup_handling": "Follow-up",
        "weighted_total": "Weighted Total",
    }
    return [
        (label_map.get(key, key), _format_score_value(value))
        for key, value in analysis.rubric.score_breakdown().items()
    ]


def _format_score_value(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _evidence_lines(analysis: TopicAnalysis) -> list[str]:
    if analysis.evidence_items:
        return [
            f"[{format_ms_range(item.start_ms, item.end_ms)}] {item.text}"
            for item in analysis.evidence_items
            if item.text.strip()
        ]
    return analysis.evidence_quotes
