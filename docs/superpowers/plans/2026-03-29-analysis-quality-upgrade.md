# Analysis Quality Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make per-question analysis output more transparent by exposing score breakdowns and evidence snippets with timestamps.

**Architecture:** Add a lightweight structured evidence model to the analysis schema, populate it in the heuristic analysis layer, and reuse it in both markdown reporting and Streamlit QA review rendering. Keep the existing fallback-friendly pipeline and avoid any prompt-level changes.

**Tech Stack:** Python, Streamlit, Pydantic, pytest

---

### Task 1: Analysis Schema And Heuristic Evidence

**Files:**
- Modify: `part_b/schemas.py`
- Modify: `part_b/nodes/topic_analyzer.py`
- Modify: `core/time_utils.py`
- Create: `tests/test_analysis_quality.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Add `EvidenceSnippet`, rubric breakdown helper, and timed evidence extraction**
- [ ] **Step 4: Run test to verify it passes**

### Task 2: Report And QA Review Transparency

**Files:**
- Modify: `part_b/reporting.py`
- Modify: `ui/analysis_views.py`
- Modify: `tests/test_phase4_regressions.py`
- Modify: `tests/gates/phase4_gate.py`

- [ ] **Step 1: Extend failing tests for score breakdown and evidence timeline**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Render score breakdown and evidence timeline in report and QA review**
- [ ] **Step 4: Run test to verify it passes**

### Task 3: Verification

**Files:**
- No additional files beyond verification outputs

- [ ] **Step 1: Run targeted tests for analysis quality**
- [ ] **Step 2: Run full pytest and all phase gates**
