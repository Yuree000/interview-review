from __future__ import annotations

from pathlib import Path
from tkinter import TclError, Tk, filedialog

import streamlit as st

from config import get_settings
from part_b.schemas import StatusDocument
from services.analysis_service import AnalysisService
from ui.analysis_views import render_analysis_bundle
from ui.theme import configure_page, render_section_intro, render_stat_cards


settings = get_settings()
service = AnalysisService()
SMALL_UPLOAD_LIMIT_MB = 512
SMALL_UPLOAD_LIMIT_BYTES = SMALL_UPLOAD_LIMIT_MB * 1024 * 1024


def _candidate_paths() -> list[str]:
    roots = [
        settings.base_dir / "video_files",
        settings.base_dir / "tests" / "runtime",
    ]
    suffixes = {".mp3", ".mp4", ".wav", ".m4a", ".aac", ".flac", ".mov", ".mkv"}
    discovered: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in suffixes:
                discovered.append(str(path))
    return sorted(set(discovered))[:50]


def _save_uploaded_file(uploaded_file) -> str:
    upload_dir = settings.base_dir / "tests" / "runtime" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_path = upload_dir / uploaded_file.name
    target_path.write_bytes(uploaded_file.getbuffer())
    return str(target_path)


def _pick_local_file() -> str:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilename(
            title="Choose interview media",
            filetypes=[
                ("Audio and video", "*.mp3 *.mp4 *.wav *.m4a *.aac *.flac *.mov *.mkv"),
                ("All files", "*.*"),
            ],
        )
    finally:
        root.destroy()
    return selected


def _render_bundle(interview_id: str) -> None:
    bundle = service.load_bundle(interview_id)
    title = bundle.meta.title if bundle.meta else interview_id
    st.success(f"Loaded result: {title}")
    render_analysis_bundle(bundle)


def _run_flow(input_path: str, title: str, target_phase: str) -> None:
    progress_placeholder = st.empty()
    last_status_box = st.empty()
    collected_statuses: list[dict[str, str]] = []

    def status_callback(status: StatusDocument) -> None:
        collected_statuses.append(
            {
                "stage": status.current_stage,
                "status": status.status.value,
                "updated_at": status.updated_at,
                "last_error": status.last_error or "",
            }
        )
        last_status_box.dataframe(collected_statuses, use_container_width=True, hide_index=True)

    with st.spinner("Running the review pipeline..."):
        interview_id = service.run_preprocessing(
            input_path,
            title=title or None,
            status_callback=status_callback,
        )
        progress_placeholder.info(f"PH2 complete: {interview_id}")
        if target_phase in {"phase3", "phase4"}:
            service.run_phase3(interview_id, status_callback=status_callback)
            progress_placeholder.info(f"PH3 complete: {interview_id}")
        if target_phase == "phase4":
            service.run_phase4(interview_id, status_callback=status_callback)
            progress_placeholder.info(f"PH4 complete: {interview_id}")

    st.session_state["new_analysis_last_interview_id"] = interview_id


if "new_analysis_input_path" not in st.session_state:
    st.session_state["new_analysis_input_path"] = ""
if "new_analysis_selected_path" not in st.session_state:
    st.session_state["new_analysis_selected_path"] = ""

recent_paths = _candidate_paths()

configure_page(
    title="New Analysis",
    subtitle=(
        "Choose a local media file and let the app run transcript generation, QA extraction, "
        "reference answers, and the final report in one pass."
    ),
    active_path="pages/new_analysis.py",
    eyebrow="Run Pipeline",
    badges=[
        "Full flow by default",
        "Large MP4 via local path",
        "Small upload fallback available",
    ],
    sidebar_facts=[
        ("Ready files", str(len(recent_paths))),
        ("Default flow", "PH2 -> PH4"),
        ("Upload fallback", f"{SMALL_UPLOAD_LIMIT_MB}MB"),
    ],
)

render_stat_cards(
    [
        ("Discovered files", str(len(recent_paths)), "Media files visible under common workspace folders"),
        ("Primary input", "Local path", "Best for multi-GB recordings and screen captures"),
        ("Fallback upload", f"{SMALL_UPLOAD_LIMIT_MB}MB", "Use only for quick small-file experiments"),
    ]
)

controls_col, guide_col = st.columns([1.2, 0.8], gap="large")

selected_path = st.selectbox(
    "Quick pick from workspace",
    options=[""] + recent_paths,
    index=0,
    help="This scans common project folders only. You can still paste any full local path.",
)
if selected_path and selected_path != st.session_state["new_analysis_selected_path"]:
    st.session_state["new_analysis_input_path"] = selected_path
st.session_state["new_analysis_selected_path"] = selected_path

with controls_col:
    with st.container(border=True):
        st.markdown("#### Source")
        render_section_intro("Use a local path as the default input mode. It avoids browser-side copy overhead on large files.")

        picker_col, path_col = st.columns([1, 2.4], gap="medium")
        with picker_col:
            if st.button("Open native picker", use_container_width=True):
                try:
                    picked_path = _pick_local_file()
                except TclError as exc:
                    st.error(f"Unable to open file picker: {exc}")
                else:
                    if picked_path:
                        st.session_state["new_analysis_input_path"] = picked_path
                        st.session_state["new_analysis_selected_path"] = ""
                        st.rerun()
        with path_col:
            st.text_input(
                "Local file path",
                key="new_analysis_input_path",
                placeholder=r"E:\path\to\interview.mp4",
                help="Recommended for large media. The app reads the file in place instead of re-uploading it.",
            )

        st.text_input("Optional title", key="new_analysis_title", placeholder="Defaults to the source filename")

        effective_path = st.session_state["new_analysis_input_path"].strip()
        if effective_path:
            candidate = Path(effective_path)
            st.caption(
                f"Current selection: {effective_path}"
                + (f" | Exists: {'yes' if candidate.exists() else 'no'}" if effective_path else "")
            )

        with st.expander("Fallback: upload a small file", expanded=False):
            st.caption(
                "Keep uploads for small experiments only. Large recordings are much faster and more stable through local paths."
            )
            uploaded_file = st.file_uploader(
                "Upload a small audio/video file",
                type=["mp3", "mp4", "wav", "m4a", "aac", "flac", "mov", "mkv"],
                help=f"Fallback mode only. Files above {SMALL_UPLOAD_LIMIT_MB}MB are rejected in the UI.",
            )
            if uploaded_file is not None:
                size_bytes = int(getattr(uploaded_file, "size", 0) or 0)
                if size_bytes > SMALL_UPLOAD_LIMIT_BYTES:
                    st.error(f"Upload is limited to {SMALL_UPLOAD_LIMIT_MB}MB in fallback mode. Use a local path instead.")
                else:
                    saved_path = _save_uploaded_file(uploaded_file)
                    st.session_state["new_analysis_input_path"] = saved_path
                    st.info(f"Saved upload to: {saved_path}")

with guide_col:
    with st.container(border=True):
        st.markdown("#### Run mode")
        render_section_intro("For normal use, run the full pipeline and let the app generate the final report automatically.")
        st.write("- PH2: input validation, audio extraction, and transcript generation")
        st.write("- PH3: role detection, context completion, and QA extraction")
        st.write("- PH4: reference answers, per-question review, and final report")
        st.info("The main button below already runs the full path. Stage buttons are left here only for debugging.")

effective_path = st.session_state["new_analysis_input_path"].strip()
title = st.session_state.get("new_analysis_title", "").strip()

run_full = st.button("Start full analysis", type="primary", use_container_width=True)
with st.expander("Debug: run to a specific phase", expanded=False):
    debug_cols = st.columns(3)
    run_phase2 = debug_cols[0].button("Run to PH2", use_container_width=True)
    run_phase3 = debug_cols[1].button("Run to PH3", use_container_width=True)
    run_phase4 = debug_cols[2].button("Run to PH4", use_container_width=True)

if run_full or run_phase2 or run_phase3 or run_phase4:
    if not effective_path:
        st.error("Choose a local file, paste a full path, or use the small-file upload fallback first.")
    elif not Path(effective_path).exists():
        st.error(f"File not found: {effective_path}")
    else:
        target_phase = "phase4" if run_full else "phase2"
        if run_phase3:
            target_phase = "phase3"
        if run_phase4:
            target_phase = "phase4"
        try:
            _run_flow(effective_path, title, target_phase)
        except Exception as exc:
            st.exception(exc)

last_interview_id = st.session_state.get("new_analysis_last_interview_id", "")
if last_interview_id:
    st.write("")
    with st.container(border=True):
        st.markdown("#### Latest run")
        try:
            _render_bundle(last_interview_id)
        except Exception as exc:
            st.session_state.pop("new_analysis_last_interview_id", None)
            st.warning(f"Unable to reload the latest result: {exc}")
