from __future__ import annotations

import streamlit as st

from services.capability_service import CapabilityService
from services.interview_repo import InterviewRepository
from services.profile_service import ProfileService
from ui.theme import configure_page, render_list_block, render_section_intro, render_stat_cards


repository = InterviewRepository()
profile_service = ProfileService(output_root=repository.output_root)
capability_service = CapabilityService(repository=repository, profile_service=profile_service)
items = repository.list_all()

global_profile = profile_service.get_global_profile()
global_markdown = profile_service.get_global_profile_markdown()

configure_page(
    title="Profile",
    subtitle="Refresh and read the multi-interview capability profile together with single-run snapshots.",
    active_path="pages/profile.py",
    eyebrow="Longitudinal Review",
    badges=[
        "Global profile",
        "Single-run snapshots",
        "Refresh controls",
    ],
    sidebar_facts=[
        ("Saved runs", str(len(items))),
        ("Global profile", "Ready" if global_profile else "Pending"),
        ("Snapshots", str(len([item for item in items if item.interview_id]))),
    ],
)

render_stat_cards(
    [
        ("Saved runs", str(len(items)), "Interview runs available for snapshot refresh"),
        ("Global profile", "Ready" if global_profile else "Pending", "Aggregated capability summary"),
        ("Markdown view", "Ready" if global_markdown else "Pending", "Human-readable profile summary"),
    ]
)

top_col1, top_col2 = st.columns(2, gap="large")
with top_col1:
    with st.container(border=True):
        st.markdown("#### Refresh global profile")
        render_section_intro("Recompute the profile after you add new completed analyses.")
        if st.button("Refresh global profile", type="primary", use_container_width=True):
            try:
                capability_service.refresh_global_profile()
            except Exception as exc:
                st.exception(exc)
            else:
                st.success("Global profile refreshed.")
                st.rerun()

with top_col2:
    refreshable_ids = [item.interview_id for item in items if item.interview_id]
    with st.container(border=True):
        st.markdown("#### Refresh one snapshot")
        render_section_intro("Recompute a single interview snapshot without touching the aggregated profile.")
        selected_for_snapshot = st.selectbox("Interview id", options=[""] + refreshable_ids, index=0)
        if selected_for_snapshot and st.button("Refresh selected snapshot", use_container_width=True):
            try:
                capability_service.refresh_snapshot(selected_for_snapshot)
            except Exception as exc:
                st.exception(exc)
            else:
                st.success("Interview snapshot refreshed.")
                st.rerun()

st.write("")
with st.container(border=True):
    st.markdown("#### Global profile")
    if global_profile is None:
        render_section_intro("No global profile has been created yet. Complete PH4 on at least one interview and refresh here.")
        st.info("Global profile not available yet.")
    else:
        render_section_intro("A condensed view of public dimensions, strengths, weaknesses, and the learning roadmap.")
        st.write(global_profile.trend_summary)
        if global_profile.public_dimensions:
            st.dataframe(
                [{"dimension": name, "score": score} for name, score in global_profile.public_dimensions.items()],
                use_container_width=True,
                hide_index=True,
            )

        left, right = st.columns(2, gap="large")
        with left:
            render_list_block("Strengths", global_profile.strengths, empty_message="No strengths captured yet.")
            st.write("")
            render_list_block("Learning roadmap", global_profile.learning_roadmap, empty_message="No roadmap captured yet.")
        with right:
            render_list_block("Weaknesses", global_profile.weaknesses, empty_message="No weaknesses captured yet.")
            st.write("")
            st.markdown("##### Role-specific dimensions")
            if global_profile.role_dimensions:
                for role_name, dimensions in global_profile.role_dimensions.items():
                    st.markdown(f"**{role_name}**")
                    st.dataframe(
                        [{"dimension": name, "score": score} for name, score in dimensions.items()],
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.info("No role-specific dimensions available yet.")

        if global_markdown:
            with st.expander("Open markdown summary", expanded=False):
                st.markdown(global_markdown)

st.write("")
with st.container(border=True):
    st.markdown("#### Single interview snapshot")
    if not items:
        render_section_intro("Snapshots appear after at least one interview run has saved analysis artifacts.")
        st.info("No interview records available yet.")
    else:
        selected_id = st.selectbox("Choose an interview", options=[item.interview_id for item in items], index=0)
        snapshot = repository.load_capability_snapshot(selected_id)
        meta = repository.load_meta(selected_id)
        if snapshot is None:
            render_section_intro("The selected run does not have a snapshot yet. Use the refresh control above.")
            st.warning("Snapshot not available for this run.")
        else:
            render_section_intro("Public dimensions and the next focus items for the selected run.")
            st.markdown(f"**Title:** {meta.title if meta else selected_id}")
            st.markdown(f"**Target position:** {meta.target_position if meta and meta.target_position else 'unknown'}")
            st.markdown(f"**Updated at:** {snapshot.updated_at}")
            st.dataframe(
                [{"dimension": name, "score": score} for name, score in snapshot.public_dimensions.items()],
                use_container_width=True,
                hide_index=True,
            )
            left, right = st.columns(2, gap="large")
            with left:
                render_list_block("Strengths", snapshot.strengths, empty_message="No strengths recorded.")
            with right:
                render_list_block("Weaknesses", snapshot.weaknesses, empty_message="No weaknesses recorded.")
            st.write("")
            render_list_block("Next focus", snapshot.next_focus, empty_message="No next focus items recorded.")
            st.info(snapshot.summary)
