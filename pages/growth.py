from __future__ import annotations

import streamlit as st

from services.compare_service import CompareService
from services.interview_repo import InterviewRepository
from ui.theme import configure_page, render_list_block, render_section_intro, render_stat_cards


repository = InterviewRepository()
compare_service = CompareService(repository=repository)
items = repository.list_all()

configure_page(
    title="Growth",
    subtitle="Compare two interview runs and focus on improvements, regressions, and repeated issues.",
    active_path="pages/growth.py",
    eyebrow="Compare Runs",
    badges=[
        "Delta by dimension",
        "Repeated issues",
        "Next focus",
    ],
    sidebar_facts=[
        ("Saved runs", str(len(items))),
        ("Comparable", str(len(items)) if len(items) >= 2 else "Need 2"),
        ("Mode", "Side-by-side"),
    ],
)

render_stat_cards(
    [
        ("Saved runs", str(len(items)), "Repository entries available for comparison"),
        ("Minimum needed", "2", "You need at least two runs for a useful delta view"),
        ("Current status", "Ready" if len(items) >= 2 else "Blocked", "Comparison can start once two runs exist"),
    ]
)

if len(items) < 2:
    with st.container(border=True):
        st.markdown("#### Comparison unavailable")
        render_section_intro("Growth view unlocks after at least two interviews have completed enough of the pipeline.")
        st.info("Add one more PH4-complete interview before returning here.")
else:
    options = [
        f"{item.interview_id} | {item.title or item.interview_id} | {item.target_position or 'unknown target'}"
        for item in items
    ]
    option_to_id = {option: option.split(" | ", 1)[0] for option in options}

    with st.container(border=True):
        st.markdown("#### Select the two runs")
        render_section_intro("Choose a baseline and a newer run. The output emphasizes what changed and what still repeats.")
        col1, col2 = st.columns(2)
        selected_a = col1.selectbox("Baseline A", options=options, index=min(1, len(options) - 1))
        selected_b = col2.selectbox("Comparison B", options=options, index=0)

        if option_to_id[selected_a] == option_to_id[selected_b]:
            st.warning("Choose two different interview runs.")
        elif st.button("Compare selected interviews", type="primary", use_container_width=True):
            try:
                payload = compare_service.compare(option_to_id[selected_a], option_to_id[selected_b])
            except Exception as exc:
                st.exception(exc)
            else:
                st.write("")
                with st.container(border=True):
                    st.markdown("#### Summary")
                    st.markdown(payload.summary_markdown)

                with st.container(border=True):
                    st.markdown("#### Public-dimension delta")
                    st.dataframe(
                        [
                            {"dimension": name, "delta": delta}
                            for name, delta in payload.public_dimension_delta.items()
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )

                if payload.role_dimension_delta:
                    with st.container(border=True):
                        st.markdown("#### Role and topic delta")
                        st.dataframe(
                            [
                                {"dimension": name, "delta": delta}
                                for name, delta in payload.role_dimension_delta.items()
                            ],
                            use_container_width=True,
                            hide_index=True,
                        )

                if payload.topic_deltas:
                    with st.container(border=True):
                        st.markdown("#### Shared-question delta")
                        st.dataframe(
                            [
                                {
                                    "topic": item.topic_key,
                                    "score_a": item.score_a,
                                    "score_b": item.score_b,
                                    "delta": item.delta,
                                    "summary_a": item.summary_a,
                                    "summary_b": item.summary_b,
                                }
                                for item in payload.topic_deltas
                            ],
                            use_container_width=True,
                            hide_index=True,
                        )

                left, right = st.columns(2, gap="large")
                with left:
                    with st.container(border=True):
                        render_list_block("Improvements", payload.result.improvements, empty_message="No improvements captured.")
                        st.write("")
                        render_list_block("Repeated issues", payload.result.repeated_issues, empty_message="No repeated issues captured.")
                with right:
                    with st.container(border=True):
                        render_list_block("Regressions", payload.result.regressions, empty_message="No regressions captured.")
                        st.write("")
                        render_list_block("Next focus", payload.result.next_focus, empty_message="No next focus points captured.")
