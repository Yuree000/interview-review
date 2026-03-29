from __future__ import annotations

import json

import streamlit as st

from services.analysis_service import AnalysisService
from ui.analysis_views import render_analysis_bundle
from ui.theme import configure_page, render_section_intro, render_stat_cards


service = AnalysisService()
all_items = service.list_interviews()


def _rerun_options(bundle) -> dict[str, str]:
    options: dict[str, str] = {}
    if bundle.transcription is not None and bundle.meta is not None:
        options["B1"] = "B1 · Rebuild role/context/QA/report"
    if bundle.qa_pairs is not None and bundle.meta is not None:
        options["B4"] = "B4 · Rebuild analyses/report/profile"
    if bundle.analyses is not None:
        options["B6"] = "B6 · Refresh snapshot/profile only"
    return options

configure_page(
    title="History",
    subtitle="Filter saved interviews and read the transcript, extracted QA review set, and final report.",
    active_path="pages/history.py",
    eyebrow="Read Outputs",
    badges=[
        "Single-run review",
        "Transcript + QA + report",
        "Filter by stage and title",
    ],
    sidebar_facts=[
        ("Saved runs", str(len(all_items))),
        ("Completed", str(sum(1 for item in all_items if item.current_stage in {"B5", "B6"}))),
        ("Latest stage", all_items[0].current_stage if all_items else "none"),
    ],
)

status_options = sorted({item.status for item in all_items if item.status})
selected_status = st.selectbox("Status", options=["all"] + status_options, index=0)
title_keyword = st.text_input("Title contains", placeholder="Filter by title")
position_keyword = st.text_input("Target position contains", placeholder="Filter by target role")

filtered_items = []
for item in all_items:
    if selected_status != "all" and item.status != selected_status:
        continue
    if title_keyword.strip() and title_keyword.strip().lower() not in (item.title or "").lower():
        continue
    if position_keyword.strip() and position_keyword.strip().lower() not in (item.target_position or "").lower():
        continue
    filtered_items.append(item)

render_stat_cards(
    [
        ("All runs", str(len(all_items)), "Total repository entries"),
        ("Filtered", str(len(filtered_items)), "Runs matching the current filters"),
        (
            "Report-ready",
            str(sum(1 for item in filtered_items if item.current_stage in {"B5", "B6"})),
            "Filtered runs that already produced report artifacts",
        ),
    ]
)

with st.container(border=True):
    st.markdown("#### Result list")
    render_section_intro("Use the table to scan status and then open a specific interview below.")
    if filtered_items:
        st.dataframe(
            [
                {
                    "interview_id": item.interview_id,
                    "status": item.status,
                    "stage": item.current_stage,
                    "title": item.title,
                    "target_position": item.target_position,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                }
                for item in filtered_items
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No records match the current filter set.")

selected_interview_id = st.selectbox(
    "Open one interview",
    options=[""] + [item.interview_id for item in filtered_items],
    index=0,
)

if selected_interview_id:
    bundle = service.load_bundle(selected_interview_id)
    rerun_options = _rerun_options(bundle)
    bundle_payload = service.export_bundle_payload(selected_interview_id)
    st.write("")
    with st.container(border=True):
        st.markdown("#### Interview detail")
        if bundle.meta is not None:
            st.caption(f"{bundle.meta.title or selected_interview_id} | {bundle.meta.source_file_name}")
        if bundle.status is not None:
            st.caption(f"Pipeline status: {bundle.status.status.value} | Current stage: {bundle.status.current_stage}")

        actions_col, export_col = st.columns([1.05, 0.95], gap="large")
        with actions_col:
            st.markdown("##### Workflow actions")
            if rerun_options:
                rerun_label = st.selectbox(
                    "Rerun from saved stage",
                    options=[""] + list(rerun_options.values()),
                    index=0,
                    key=f"history_rerun_{selected_interview_id}",
                    help="Use saved artifacts to rerun later stages without re-uploading the source file.",
                )
                rerun_stage = next(
                    (stage for stage, label in rerun_options.items() if label == rerun_label),
                    "",
                )
                if st.button(
                    "Run selected stage",
                    disabled=not rerun_stage,
                    use_container_width=True,
                    key=f"history_rerun_button_{selected_interview_id}",
                ):
                    try:
                        final_status = service.rerun_from_stage(selected_interview_id, rerun_stage)
                    except Exception as exc:
                        st.exception(exc)
                    else:
                        st.success(
                            f"Rerun finished at {final_status.current_stage} with status {final_status.status.value}."
                        )
                        st.rerun()
            else:
                st.info("No rerunnable stage is available for this interview yet.")

        with export_col:
            st.markdown("##### Export")
            st.download_button(
                "Download report markdown",
                data=bundle.report_markdown or "",
                file_name=f"{selected_interview_id}-report.md",
                disabled=not bundle.report_markdown,
                use_container_width=True,
            )
            st.download_button(
                "Download bundle JSON",
                data=json.dumps(bundle_payload, ensure_ascii=False, indent=2),
                file_name=f"{selected_interview_id}-bundle.json",
                mime="application/json",
                use_container_width=True,
            )

        render_analysis_bundle(bundle)
