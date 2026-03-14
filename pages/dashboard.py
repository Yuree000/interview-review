from __future__ import annotations

import streamlit as st

from services.capability_service import CapabilityService
from services.interview_repo import InterviewRepository
from services.profile_service import ProfileService
from ui.theme import configure_page, render_list_block, render_section_intro, render_stat_cards


repository = InterviewRepository()
profile_service = ProfileService(output_root=repository.output_root)
capability_service = CapabilityService(repository=repository, profile_service=profile_service)

records = repository.list_all()
global_profile = profile_service.get_global_profile()
resume = profile_service.get_resume()


def _stage_distribution() -> dict[str, int]:
    distribution: dict[str, int] = {}
    for item in records:
        key = item.current_stage or "unknown"
        distribution[key] = distribution.get(key, 0) + 1
    return distribution


configure_page(
    title="Dashboard",
    subtitle="Track pipeline coverage, recent outputs, and the current operational backlog in one view.",
    active_path="pages/dashboard.py",
    eyebrow="Operations",
    badges=[
        "High-level metrics",
        "Recent runs",
        "Profile refresh actions",
    ],
    sidebar_facts=[
        ("Records", str(len(records))),
        ("Resume", "Ready" if resume else "Missing"),
        ("Profile", "Ready" if global_profile else "Pending"),
    ],
)

render_stat_cards(
    [
        ("Total interviews", str(len(records)), "Every saved interview run in the repository"),
        ("PH4 ready", str(sum(1 for item in records if item.current_stage in {"B5", "B6"})), "Runs with analysis/report artifacts"),
        ("Resume", "Ready" if resume else "Missing", "Candidate background coverage"),
        ("Profile", "Ready" if global_profile else "Pending", "Aggregated capability summary"),
    ]
)

actions: list[str] = []
if not resume:
    actions.append("Import a resume so phase 3 and phase 4 have stronger background context.")
if not records:
    actions.append("Complete the first analysis run from New Analysis.")
if len(records) == 1:
    actions.append("Add one more full interview so Growth comparison becomes meaningful.")
if records and global_profile is None:
    actions.append("Refresh the global profile after a completed PH4 run.")
if not actions:
    actions.append("Use History and Growth to review one run deeply and compare two runs side by side.")

left, right = st.columns([1, 1], gap="large")
with left:
    with st.container(border=True):
        st.markdown("#### Action queue")
        render_section_intro("The minimum set of actions that keeps the review workspace useful.")
        render_list_block("Backlog", actions, empty_message="No immediate dashboard actions.")

with right:
    with st.container(border=True):
        st.markdown("#### Stage distribution")
        render_section_intro("A quick histogram of how far saved runs have progressed.")
        distribution = _stage_distribution()
        if distribution:
            st.bar_chart(distribution)
        else:
            st.info("No interview records yet.")

st.write("")
with st.container(border=True):
    st.markdown("#### Recent runs")
    render_section_intro("Most recent interviews, including stage and detected target position.")
    if records:
        st.dataframe(
            [
                {
                    "interview_id": item.interview_id,
                    "title": item.title,
                    "status": item.status,
                    "stage": item.current_stage,
                    "target_position": item.target_position,
                    "updated_at": item.updated_at,
                }
                for item in records[:10]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No interview records available yet.")

if global_profile is not None:
    st.write("")
    with st.container(border=True):
        st.markdown("#### Global profile snapshot")
        render_section_intro("A short read on where the candidate currently looks strongest and weakest.")
        st.write(global_profile.trend_summary)
        st.dataframe(
            [{"dimension": name, "score": score} for name, score in global_profile.public_dimensions.items()],
            use_container_width=True,
            hide_index=True,
        )
        strengths_col, weaknesses_col = st.columns(2, gap="large")
        with strengths_col:
            render_list_block("Strengths", global_profile.strengths[:5], empty_message="No strengths captured yet.")
        with weaknesses_col:
            render_list_block("Weaknesses", global_profile.weaknesses[:5], empty_message="No weaknesses captured yet.")
else:
    st.write("")
    with st.container(border=True):
        st.markdown("#### Profile refresh")
        render_section_intro("No global profile is saved yet. You can trigger a refresh directly from here.")
        if st.button("Refresh global profile", use_container_width=True):
            try:
                capability_service.refresh_global_profile()
            except Exception as exc:
                st.exception(exc)
            else:
                st.success("Global profile refreshed.")
                st.rerun()
