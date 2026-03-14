from __future__ import annotations

import streamlit as st

from core.exceptions import ProjectError
from part_b.schemas import ResumeProfileDocument, ResumeProject
from services.profile_service import ProfileService
from services.resume_ingest_service import ResumeIngestService
from ui.theme import configure_page, render_list_block, render_section_intro, render_stat_cards


service = ProfileService()
ingest_service = ResumeIngestService(profile_service=service)


def _format_projects(projects: list[ResumeProject]) -> str:
    lines: list[str] = []
    for project in projects:
        highlights = "; ".join(project.highlights)
        lines.append(f"{project.name} | {project.role or ''} | {highlights}")
    return "\n".join(lines)


def _parse_projects(raw: str) -> list[ResumeProject]:
    projects: list[ResumeProject] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = [part.strip() for part in stripped.split("|")]
        name = parts[0] if parts else ""
        role = parts[1] if len(parts) > 1 and parts[1] else None
        highlights = [item.strip() for item in (parts[2] if len(parts) > 2 else "").split(";") if item.strip()]
        if name:
            projects.append(ResumeProject(name=name, role=role, highlights=highlights))
    return projects


def _csv_to_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.replace("\n", ",").split(",") if item.strip()]


profile = service.get_resume()
upload_feedback: tuple[str, str] | None = None

configure_page(
    title="Resume",
    subtitle="Import or edit the candidate background that the QA extractor and answer reviewer can lean on.",
    active_path="pages/resume.py",
    eyebrow="Background Context",
    badges=[
        "PDF / DOCX / TXT / MD",
        "Manual editing supported",
        "Feeds later analysis stages",
    ],
    sidebar_facts=[
        ("Resume", "Ready" if profile else "Missing"),
        ("Projects", str(len(profile.key_projects)) if profile else "0"),
        ("Tech stack", str(len(profile.tech_stack)) if profile else "0"),
    ],
)

render_stat_cards(
    [
        ("Resume", "Ready" if profile else "Missing", "Current saved profile status"),
        ("Projects", str(len(profile.key_projects)) if profile else "0", "Structured project entries"),
        ("Tech stack", str(len(profile.tech_stack)) if profile else "0", "Skill keywords currently stored"),
    ]
)

upload_col, info_col = st.columns([1.15, 0.85], gap="large")
with upload_col:
    with st.container(border=True):
        st.markdown("#### Import from file")
        render_section_intro("Use text-based resume files for the fastest import. You can still revise every field below.")
        uploaded_file = st.file_uploader(
            "Choose a resume file",
            type=["pdf", "docx", "txt", "md"],
            help="Only text-based resume files are supported in this version.",
        )
        import_clicked = st.button(
            "Import and parse resume",
            type="primary",
            disabled=uploaded_file is None,
            use_container_width=True,
        )

        if import_clicked and uploaded_file is not None:
            try:
                result = ingest_service.ingest_bytes(uploaded_file.name, uploaded_file.getvalue())
            except ProjectError as exc:
                upload_feedback = ("error", f"Import failed: {exc}")
            except Exception as exc:
                upload_feedback = ("error", f"Import failed: {type(exc).__name__}: {exc}")
            else:
                profile = result.profile
                upload_feedback = ("success", f"Imported {uploaded_file.name}. You can still revise the fields below before saving.")

        if upload_feedback is not None:
            level, message = upload_feedback
            if level == "success":
                st.success(message)
            else:
                st.error(message)

with info_col:
    with st.container(border=True):
        st.markdown("#### Import notes")
        render_section_intro("The parser extracts structure, but the final quality still depends on a quick human pass.")
        st.write("- Supported formats: PDF, DOCX, TXT, MD")
        st.write("- The parser tries to pull out target roles, tech stack, projects, and raw text")
        st.write("- Review the generated profile before using it for later interview analysis")
        st.write("")
        st.markdown("##### Project entry format")
        st.caption("One project per line: `Project name | Role | Highlight 1; Highlight 2; Highlight 3`")

profile = service.get_resume()
with st.form("resume_form"):
    left, right = st.columns(2, gap="large")
    with left:
        name = st.text_input("Name", value=profile.name if profile else "")
        target_positions = st.text_input(
            "Target positions",
            value=", ".join(profile.target_positions) if profile else "",
            help="Separate multiple target roles with commas.",
        )
        years_of_experience = st.number_input(
            "Years of experience",
            min_value=0.0,
            max_value=40.0,
            step=0.5,
            value=float(profile.years_of_experience) if profile and profile.years_of_experience is not None else 0.0,
        )
        education = st.text_input("Education", value=profile.education if profile and profile.education else "")
    with right:
        tech_stack = st.text_area(
            "Tech stack",
            value=", ".join(profile.tech_stack) if profile else "",
            height=110,
            help="Comma-separated, for example: Java, Spring Boot, Redis, MySQL",
        )
        projects_raw = st.text_area(
            "Key projects",
            value=_format_projects(profile.key_projects) if profile else "",
            height=180,
        )

    raw_text = st.text_area(
        "Raw resume text",
        value=profile.raw_text if profile and profile.raw_text else "",
        height=220,
    )
    submitted = st.form_submit_button("Save resume", type="primary")

if submitted:
    document = ResumeProfileDocument(
        name=name or None,
        target_positions=_csv_to_list(target_positions),
        years_of_experience=years_of_experience,
        tech_stack=_csv_to_list(tech_stack),
        education=education or None,
        key_projects=_parse_projects(projects_raw),
        raw_text=raw_text or None,
    )
    service.update_resume(document)
    st.success("Resume saved.")
    st.rerun()

action_col1, action_col2 = st.columns(2, gap="large")
with action_col1:
    if st.button("Delete saved resume", type="secondary", use_container_width=True):
        service.delete_resume()
        st.warning("Resume deleted.")
        st.rerun()
with action_col2:
    if st.button("Refresh page", use_container_width=True):
        st.rerun()

profile = service.get_resume()
st.write("")
with st.container(border=True):
    st.markdown("#### Current resume snapshot")
    if profile is None:
        render_section_intro("No saved resume is available yet.")
        st.info("Import or save a resume to populate this section.")
    else:
        render_section_intro("This is the structured profile currently used by later review stages.")
        left, right = st.columns(2, gap="large")
        with left:
            st.markdown(f"**Name:** {profile.name or 'Not set'}")
            st.markdown(f"**Target positions:** {', '.join(profile.target_positions) or 'Not set'}")
            st.markdown(
                f"**Years of experience:** {profile.years_of_experience if profile.years_of_experience is not None else 'Not set'}"
            )
            st.markdown(f"**Education:** {profile.education or 'Not set'}")
        with right:
            render_list_block("Tech stack", profile.tech_stack, empty_message="No tech stack recorded.")

        st.write("")
        render_list_block(
            "Key projects",
            [
                f"{project.name} | {project.role or 'role not set'} | {'; '.join(project.highlights) or 'no highlights'}"
                for project in profile.key_projects
            ],
            empty_message="No projects recorded.",
        )

        if profile.raw_text:
            st.write("")
            st.markdown("##### Raw text preview")
            st.text_area("raw_resume_preview", value=profile.raw_text, height=220, disabled=True, label_visibility="collapsed")
