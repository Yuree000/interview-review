from __future__ import annotations

import json

import streamlit as st

from services.compare_service import CompareService
from services.interview_repo import InterviewRepository
from services.trend_service import TrendService
from ui.theme import configure_page, render_list_block, render_section_intro, render_stat_cards


repository = InterviewRepository()
compare_service = CompareService(repository=repository)
trend_service = TrendService(repository=repository)
items = repository.list_all()
trend_payload = None
trend_error: Exception | None = None

if len(items) >= 2:
    try:
        trend_payload = trend_service.build_payload()
    except Exception as exc:  # pragma: no cover - UI fallback only
        trend_error = exc

configure_page(
    title="Growth",
    subtitle="Track multi-run trend movement, then compare two runs to isolate improvements, regressions, and repeated issues.",
    active_path="pages/growth.py",
    eyebrow="Compare Runs",
    badges=[
        "Trend overview",
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
        (
            "Trend status",
            "Ready" if trend_payload and len(trend_payload.points) >= 2 else "Need 2",
            "Trend view unlocks after at least two usable runs",
        ),
        (
            "Overall delta",
            f"{trend_payload.highlights.overall_delta:+.1f}" if trend_payload and trend_payload.points else "--",
            "Latest overall score minus earliest overall score",
        ),
        ("Current status", "Ready" if len(items) >= 2 else "Blocked", "Comparison can start once two runs exist"),
    ]
)

with st.container(border=True):
    st.markdown("#### Trend overview")
    render_section_intro("Use the longitudinal view to see whether your overall score and repeated issues are moving in the right direction.")
    if trend_error is not None:
        st.exception(trend_error)
    elif trend_payload is None or len(trend_payload.points) < 2:
        st.info("Trend view needs at least two saved runs with usable analysis artifacts.")
    else:
        trend_cols = st.columns(4)
        trend_cols[0].metric("Run Count", str(trend_payload.highlights.run_count))
        trend_cols[1].metric("Overall Delta", f"{trend_payload.highlights.overall_delta:+.1f}")
        trend_cols[2].metric("Best Improved", trend_payload.highlights.best_improved_dimension or "暂无")
        trend_cols[3].metric("Biggest Regression", trend_payload.highlights.biggest_regression_dimension or "暂无")

        chart_rows = [{"label": f"{index + 1}", "overall": point.overall} for index, point in enumerate(trend_payload.points)]
        st.line_chart(chart_rows, x="label", y="overall")

        st.dataframe(
            [
                {
                    "run": index + 1,
                    "interview_id": point.interview_id,
                    "title": point.title,
                    "target_position": point.target_position or "unknown",
                    "overall": point.overall,
                    "updated_at": point.updated_at,
                }
                for index, point in enumerate(trend_payload.points)
            ],
            use_container_width=True,
            hide_index=True,
        )

        left, right = st.columns(2, gap="large")
        with left:
            st.markdown("##### Dimension delta")
            st.dataframe(
                [
                    {"dimension": name, "delta": delta}
                    for name, delta in trend_payload.dimension_delta.items()
                ],
                use_container_width=True,
                hide_index=True,
            )
        with right:
            render_list_block(
                "Recent repeated weaknesses",
                trend_payload.recent_repeated_weaknesses,
                empty_message="No repeated weaknesses captured yet.",
            )

        export_left, export_right = st.columns(2, gap="large")
        with export_left:
            st.download_button(
                "Download trend markdown",
                data=trend_payload.summary_markdown,
                file_name="growth-trend.md",
                use_container_width=True,
            )
        with export_right:
            st.download_button(
                "Download trend JSON",
                data=json.dumps(trend_service.export_payload(trend_payload), ensure_ascii=False, indent=2),
                file_name="growth-trend.json",
                mime="application/json",
                use_container_width=True,
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
                summary_cols = st.columns(4)
                summary_cols[0].metric("Weighted Total Delta", f"{payload.highlights.weighted_total_delta:+.1f}")
                summary_cols[1].metric("Best Improved", payload.highlights.best_improved_dimension or "暂无")
                summary_cols[2].metric("Biggest Regression", payload.highlights.biggest_regression_dimension or "暂无")
                summary_cols[3].metric("Shared Topics", str(payload.highlights.shared_topic_count))

                with st.container(border=True):
                    st.markdown("#### Summary")
                    st.markdown(payload.summary_markdown)

                export_payload = compare_service.export_payload(payload)
                export_left, export_right = st.columns(2, gap="large")
                with export_left:
                    st.download_button(
                        "Download summary markdown",
                        data=payload.summary_markdown,
                        file_name=f"{payload.interview_id_a}-vs-{payload.interview_id_b}.md",
                        use_container_width=True,
                    )
                with export_right:
                    st.download_button(
                        "Download comparison JSON",
                        data=json.dumps(export_payload, ensure_ascii=False, indent=2),
                        file_name=f"{payload.interview_id_a}-vs-{payload.interview_id_b}.json",
                        mime="application/json",
                        use_container_width=True,
                    )

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
