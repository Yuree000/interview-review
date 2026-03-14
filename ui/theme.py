from __future__ import annotations

from dataclasses import dataclass
from html import escape

import streamlit as st


@dataclass(frozen=True)
class NavItem:
    path: str
    label: str
    note: str


APP_NAVIGATION: tuple[NavItem, ...] = (
    NavItem("app.py", "Overview", "Workspace status and next actions"),
    NavItem("pages/new_analysis.py", "New Analysis", "Run the full review pipeline"),
    NavItem("pages/history.py", "History", "Read transcript, QA, and reports"),
    NavItem("pages/resume.py", "Resume", "Maintain candidate background"),
    NavItem("pages/dashboard.py", "Dashboard", "Review pipeline coverage and trends"),
    NavItem("pages/growth.py", "Growth", "Compare two interviews side by side"),
    NavItem("pages/profile.py", "Profile", "Refresh and read the global profile"),
)


def configure_page(
    *,
    title: str,
    subtitle: str,
    active_path: str,
    eyebrow: str = "Interview Review",
    badges: list[str] | None = None,
    sidebar_facts: list[tuple[str, str]] | None = None,
) -> None:
    st.set_page_config(page_title=f"{title} | Interview Review", layout="wide")
    apply_theme()
    render_sidebar(active_path=active_path, facts=sidebar_facts or [])
    render_page_header(title=title, subtitle=subtitle, eyebrow=eyebrow, badges=badges or [])


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          color-scheme: light;
        }

        .stApp {
          background:
            radial-gradient(circle at top left, rgba(224, 163, 58, 0.18), transparent 28%),
            radial-gradient(circle at top right, rgba(15, 118, 110, 0.12), transparent 24%),
            linear-gradient(180deg, #f7f2e8 0%, #f3ecdf 44%, #efe5d6 100%);
        }

        [data-testid="stHeader"] {
          background: rgba(247, 242, 232, 0.72);
          backdrop-filter: blur(16px);
        }

        [data-testid="stToolbar"] {
          right: 1rem;
        }

        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #16312e 0%, #224440 100%);
          border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        [data-testid="stSidebar"] * {
          color: #f7f1e8;
        }

        .sidebar-brand,
        .sidebar-panel {
          border: 1px solid rgba(255, 255, 255, 0.12);
          background: rgba(255, 255, 255, 0.08);
          border-radius: 24px;
          padding: 1rem 1rem 1.1rem;
          margin-bottom: 1rem;
          backdrop-filter: blur(14px);
        }

        .sidebar-brand h1 {
          font-size: 1.22rem;
          margin: 0.2rem 0 0.3rem;
          letter-spacing: -0.02em;
        }

        .sidebar-eyebrow,
        .sidebar-section-title,
        .section-kicker,
        .hero-eyebrow,
        .metric-label {
          text-transform: uppercase;
          letter-spacing: 0.16em;
          font-size: 0.72rem;
        }

        .sidebar-eyebrow,
        .sidebar-section-title {
          opacity: 0.72;
        }

        .sidebar-facts {
          display: grid;
          gap: 0.55rem;
          margin-top: 0.9rem;
        }

        .sidebar-fact {
          display: flex;
          justify-content: space-between;
          gap: 0.8rem;
          align-items: center;
          padding: 0.55rem 0.75rem;
          border-radius: 999px;
          background: rgba(0, 0, 0, 0.12);
          font-size: 0.92rem;
        }

        [data-testid="stSidebar"] .stButton {
          margin-bottom: 0.45rem;
        }

        [data-testid="stSidebar"] .stButton button {
          width: 100%;
          justify-content: flex-start;
          border-radius: 18px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          padding: 0.72rem 0.9rem;
          background: rgba(255, 255, 255, 0.07);
          color: #f7f1e8;
        }

        [data-testid="stSidebar"] .stButton button:hover {
          border-color: rgba(224, 163, 58, 0.48);
          background: rgba(255, 255, 255, 0.14);
          color: #f7f1e8;
        }

        [data-testid="stSidebar"] .stButton button:disabled {
          opacity: 1;
          border-color: rgba(224, 163, 58, 0.45);
          background: rgba(224, 163, 58, 0.18);
          color: #fdf8f0;
        }

        .page-hero {
          position: relative;
          overflow: hidden;
          border: 1px solid rgba(23, 44, 40, 0.08);
          background: linear-gradient(135deg, rgba(255, 255, 255, 0.82), rgba(255, 248, 238, 0.78));
          border-radius: 32px;
          padding: 2rem 2.1rem;
          margin-bottom: 1.25rem;
          box-shadow: 0 24px 60px rgba(31, 45, 43, 0.08);
        }

        .page-hero::after {
          content: "";
          position: absolute;
          inset: auto -40px -50px auto;
          width: 180px;
          height: 180px;
          border-radius: 999px;
          background: radial-gradient(circle, rgba(224, 163, 58, 0.22), rgba(224, 163, 58, 0.0) 70%);
        }

        .hero-eyebrow {
          color: #7f7667;
          margin-bottom: 0.65rem;
        }

        .page-hero h1 {
          margin: 0;
          color: #16302d;
          font-size: 2.5rem;
          line-height: 1.02;
          letter-spacing: -0.035em;
        }

        .hero-subtitle {
          margin: 0.9rem 0 0;
          max-width: 56rem;
          color: #495b58;
          font-size: 1.02rem;
          line-height: 1.65;
        }

        .hero-badges {
          display: flex;
          flex-wrap: wrap;
          gap: 0.55rem;
          margin-top: 1.15rem;
        }

        .hero-badge {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 0.45rem 0.8rem;
          border: 1px solid rgba(23, 44, 40, 0.08);
          background: #ede1cb;
          color: #36524b;
          font-size: 0.88rem;
          font-weight: 600;
        }

        .metric-card {
          min-height: 124px;
          border-radius: 24px;
          border: 1px solid rgba(23, 44, 40, 0.08);
          background: rgba(255, 255, 255, 0.74);
          box-shadow: 0 16px 40px rgba(31, 45, 43, 0.06);
          padding: 1rem 1.1rem 1.05rem;
        }

        .metric-label {
          color: #7c7265;
        }

        .metric-value {
          margin-top: 0.55rem;
          color: #16302d;
          font-size: 2.05rem;
          font-weight: 700;
          line-height: 1;
          letter-spacing: -0.04em;
        }

        .metric-help {
          margin-top: 0.65rem;
          color: #55635f;
          font-size: 0.95rem;
          line-height: 1.45;
        }

        .section-intro {
          margin: 0.35rem 0 0.75rem;
          color: #5a6863;
          font-size: 0.98rem;
        }

        .list-block {
          display: grid;
          gap: 0.65rem;
        }

        .list-item {
          border-radius: 18px;
          background: rgba(247, 242, 232, 0.95);
          border: 1px solid rgba(23, 44, 40, 0.08);
          padding: 0.8rem 0.95rem;
          color: #243d39;
        }

        .callout-card {
          border-radius: 24px;
          border: 1px solid rgba(23, 44, 40, 0.08);
          background: rgba(255, 255, 255, 0.72);
          padding: 1rem 1.1rem;
        }

        [data-testid="stMetric"] {
          border: 1px solid rgba(23, 44, 40, 0.08);
          border-radius: 24px;
          background: rgba(255, 255, 255, 0.72);
          padding: 1rem 1.1rem;
          box-shadow: 0 16px 40px rgba(31, 45, 43, 0.06);
        }

        [data-testid="stMetricLabel"] {
          text-transform: uppercase;
          letter-spacing: 0.14em;
          color: #7c7265;
        }

        [data-testid="stMetricValue"] {
          color: #16302d;
          letter-spacing: -0.04em;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
          border-radius: 24px;
          border: 1px solid rgba(23, 44, 40, 0.08) !important;
          background: rgba(255, 255, 255, 0.72);
          box-shadow: 0 16px 40px rgba(31, 45, 43, 0.06);
        }

        [data-testid="stDataFrame"] {
          border-radius: 22px;
          overflow: hidden;
          border: 1px solid rgba(23, 44, 40, 0.08);
          background: rgba(255, 255, 255, 0.82);
        }

        [data-baseweb="tab-list"] {
          gap: 0.4rem;
          padding: 0.35rem;
          width: fit-content;
          border: 1px solid rgba(23, 44, 40, 0.08);
          border-radius: 999px;
          background: rgba(23, 44, 40, 0.06);
        }

        button[role="tab"] {
          height: auto;
          border-radius: 999px !important;
          padding: 0.5rem 0.95rem !important;
        }

        div.stButton > button,
        div.stDownloadButton > button,
        [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-primary"] {
          border-radius: 999px;
          min-height: 2.8rem;
          border: 1px solid rgba(23, 44, 40, 0.12);
          font-weight: 600;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        textarea,
        input {
          border-radius: 18px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(*, active_path: str, facts: list[tuple[str, str]]) -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
              <div class="sidebar-eyebrow">Interview Review</div>
              <h1>Interview Replay Studio</h1>
              <p>One workspace for transcript cleanup, QA extraction, answer review, and growth tracking.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if facts:
            fact_html = "".join(
                f"<div class='sidebar-fact'><span>{escape(_safe_text(label))}</span><strong>{escape(_safe_text(value))}</strong></div>"
                for label, value in facts
            )
            st.markdown(f"<div class='sidebar-panel'><div class='sidebar-facts'>{fact_html}</div></div>", unsafe_allow_html=True)

        st.markdown("<div class='sidebar-section-title'>Workspace</div>", unsafe_allow_html=True)
        for item in APP_NAVIGATION:
            is_current = item.path == active_path
            if st.button(
                item.label,
                key=f"nav_{item.path}",
                use_container_width=True,
                disabled=is_current,
            ):
                st.switch_page(item.path)

        st.markdown(
            """
            <div class="sidebar-panel">
              <div class="sidebar-section-title">Flow</div>
              <p>Use New Analysis for one-click runs, History for reading results, and Resume/Profile/Growth for longer-term review.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_page_header(*, title: str, subtitle: str, eyebrow: str, badges: list[str]) -> None:
    badge_html = "".join(f"<span class='hero-badge'>{escape(item)}</span>" for item in badges)
    st.markdown(
        f"""
        <section class="page-hero">
          <div class="hero-eyebrow">{escape(eyebrow)}</div>
          <h1>{escape(title)}</h1>
          <p class="hero-subtitle">{escape(subtitle)}</p>
          <div class="hero-badges">{badge_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_stat_cards(cards: list[tuple[str, str, str]]) -> None:
    columns = st.columns(len(cards))
    for column, (label, value, help_text) in zip(columns, cards):
        with column:
            st.markdown(
                f"""
                <div class="metric-card">
                  <div class="metric-label">{escape(label)}</div>
                  <div class="metric-value">{escape(value)}</div>
                  <div class="metric-help">{escape(help_text)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_list_block(title: str, items: list[str], *, empty_message: str) -> None:
    st.markdown(f"<div class='section-kicker'>{escape(title)}</div>", unsafe_allow_html=True)
    if not items:
        st.info(empty_message)
        return
    body = "".join(f"<div class='list-item'>{escape(item)}</div>" for item in items)
    st.markdown(f"<div class='list-block'>{body}</div>", unsafe_allow_html=True)


def render_section_intro(text: str) -> None:
    st.markdown(f"<p class='section-intro'>{escape(text)}</p>", unsafe_allow_html=True)


def _safe_text(value: object) -> str:
    if value is None:
        return "-"
    return str(value)
