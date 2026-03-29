# Growth Trend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a multi-run trend view that shows score evolution, dimension deltas, recent repeated weaknesses, and direct export from Growth.

**Architecture:** Introduce a dedicated `TrendService` that builds a repository-backed timeline payload from saved capability snapshots, then render that payload in `pages/growth.py` above the existing side-by-side comparison flow. Keep persistence unchanged and reuse existing snapshot generation paths.

**Tech Stack:** Python, Streamlit, Pydantic, pytest

---

### Task 1: Trend Service Payload

**Files:**
- Create: `services/trend_service.py`
- Create: `tests/test_trend_workflow.py`
- Modify: `services/capability_service.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run the targeted tests to verify they fail**
- [ ] **Step 3: Add timeline points, summary highlights, repeated-issue aggregation, and export payload support**
- [ ] **Step 4: Run the targeted tests to verify they pass**

### Task 2: Growth Page Trend View

**Files:**
- Modify: `pages/growth.py`
- Modify: `services/trend_service.py`
- Test: `tests/test_trend_workflow.py`

- [ ] **Step 1: Extend failing tests for page-facing payload fields**
- [ ] **Step 2: Run the targeted tests to verify they fail**
- [ ] **Step 3: Add trend metrics, line chart data, recent repeated issues, and export buttons in Growth**
- [ ] **Step 4: Run the targeted tests to verify they pass**

### Task 3: Acceptance And Verification

**Files:**
- Modify: `tests/gates/phase6_gate.py`

- [ ] **Step 1: Extend the Phase 6 gate to cover the trend service**
- [ ] **Step 2: Run targeted tests and the Phase 6 gate**
- [ ] **Step 3: Run the full pytest suite and all phase gates**
