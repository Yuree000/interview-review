from __future__ import annotations

import streamlit as st

from config import ENV_FILE, get_settings
from core.logging_config import configure_logging
from core.runtime import command_path
from services.interview_repo import InterviewRepository
from services.profile_service import ProfileService
from ui.theme import configure_page, render_list_block, render_section_intro, render_stat_cards


settings = get_settings()
settings.ensure_runtime_dirs()
configure_logging(settings.log_dir, debug=settings.debug)

repository = InterviewRepository(output_root=settings.output_dir)
profile_service = ProfileService(output_root=settings.output_dir)
records = repository.list_all()
resume = profile_service.get_resume()
global_profile = profile_service.get_global_profile()

configure_page(
    title="Workspace Overview",
    subtitle=(
        "One place for transcript generation, QA extraction, answer review, "
        "and multi-interview growth tracking."
    ),
    active_path="app.py",
    eyebrow="Command Center",
    badges=[
        f"{len(records)} interview records",
        "Local-first workflow",
        "Transcript -> QA -> report",
    ],
    sidebar_facts=[
        ("Env", settings.app_env),
        ("Records", str(len(records))),
        ("Resume", "Ready" if resume else "Missing"),
    ],
)

render_stat_cards(
    [
        ("Interviews", str(len(records)), "All saved interview runs in the workspace"),
        (
            "Reports Ready",
            str(
                sum(
                    1
                    for item in records
                    if item.current_stage in {"B5", "B6"} and item.status in {"analyzing", "completed"}
                )
            ),
            "Runs that already reached the review/report stage",
        ),
        ("Resume", "Ready" if resume else "Missing", "Candidate context for better review quality"),
        ("Global Profile", "Ready" if global_profile else "Pending", "Aggregated multi-interview capability view"),
    ]
)

left, right = st.columns([1.1, 0.9], gap="large")

next_steps: list[str] = []
if not resume:
    next_steps.append("Import a resume before the next analysis so context completion and reference answers are stronger.")
if not records:
    next_steps.append("Run the first interview from New Analysis to generate transcript, QA, and the final report.")
if records and not global_profile:
    next_steps.append("Refresh the global profile after at least one full review to see longer-term patterns.")
if not next_steps:
    next_steps.append("Use History to read single-run output and Growth to compare two interviews side by side.")

runtime_checks = [
    ("Environment file", "Ready" if ENV_FILE.exists() else "Missing"),
    ("FFmpeg", "Ready" if command_path(settings.ffmpeg_binary) is not None else "Missing"),
    ("Output root", str(settings.output_dir)),
]

with left:
    with st.container(border=True):
        st.markdown("#### Recommended next actions")
        render_section_intro("These are the fastest moves to keep the pipeline producing useful review output.")
        render_list_block("Priority queue", next_steps, empty_message="No immediate actions.")

        st.write("")
        action_cols = st.columns(3)
        with action_cols[0]:
            st.page_link("pages/new_analysis.py", label="Open New Analysis")
        with action_cols[1]:
            st.page_link("pages/history.py", label="Read History")
        with action_cols[2]:
            st.page_link("pages/resume.py", label="Update Resume")

with right:
    with st.container(border=True):
        st.markdown("#### Runtime readiness")
        render_section_intro("A quick glance at the local environment before you start another heavy media run.")
        for label, value in runtime_checks:
            st.markdown(f"**{label}**")
            st.write(value)

        if not ENV_FILE.exists():
            st.warning("`.env` is still missing. Copy `.env.example` and fill in the required keys.")
        if command_path(settings.ffmpeg_binary) is None:
            st.warning("FFmpeg is not currently discoverable by the runtime.")

st.write("")
with st.container(border=True):
    st.markdown("#### Recent interview runs")
    render_section_intro("The latest saved runs, with stage and target position at a glance.")
    if not records:
        st.info("No interview records yet. Start with New Analysis.")
    else:
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
                for item in records[:8]
            ],
            use_container_width=True,
            hide_index=True,
        )

st.write("")
with st.container(border=True):
    st.markdown("#### Navigate the workspace")
    render_section_intro("Use the pages below as the default operating rhythm for a new review cycle.")
    nav_cols = st.columns(4)
    with nav_cols[0]:
        st.page_link("pages/new_analysis.py", label="Run a new review")
        st.caption("Select a local media path and run the pipeline end to end.")
    with nav_cols[1]:
        st.page_link("pages/history.py", label="Inspect outputs")
        st.caption("Read transcript, extracted QA pairs, and the final report.")
    with nav_cols[2]:
        st.page_link("pages/growth.py", label="Compare interviews")
        st.caption("Track what improved, what repeated, and what regressed.")
    with nav_cols[3]:
        st.page_link("pages/profile.py", label="Refresh profile")
        st.caption("Update the aggregated capability profile across saved runs.")
