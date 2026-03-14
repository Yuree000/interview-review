from __future__ import annotations

import streamlit as st

from services.analysis_service import AnalysisService
from ui.analysis_views import render_analysis_bundle
from ui.theme import configure_page, render_section_intro, render_stat_cards


service = AnalysisService()
all_items = service.list_interviews()

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
    st.write("")
    with st.container(border=True):
        st.markdown("#### Interview detail")
        if bundle.meta is not None:
            st.caption(f"{bundle.meta.title or selected_interview_id} | {bundle.meta.source_file_name}")
        render_analysis_bundle(bundle)
