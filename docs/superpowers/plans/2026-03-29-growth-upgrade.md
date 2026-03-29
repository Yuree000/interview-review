# Growth Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Growth comparisons easier to trust, easier to read, and easy to export.

**Architecture:** Keep comparison logic in `services.compare_service`, add a compact highlight summary and export helper there, then expose those outputs in `pages/growth.py`. Preserve the current repository-backed model and avoid introducing new persistence files.

**Tech Stack:** Python, Streamlit, Pydantic, pytest

---

### Task 1: Compare Service Regression Coverage

**Files:**
- Create: `tests/test_compare_workflow.py`
- Modify: `services/compare_service.py`
- Test: `tests/test_compare_workflow.py`

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Add normalized topic matching, highlights, and export payload**
- [ ] **Step 4: Run test to verify it passes**

### Task 2: Growth Page Export And Summary

**Files:**
- Modify: `pages/growth.py`
- Modify: `services/compare_service.py`
- Test: `tests/test_compare_workflow.py`

- [ ] **Step 1: Write/extend failing test for new payload fields**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Add summary cards and download buttons in Growth**
- [ ] **Step 4: Run test to verify it passes**

### Task 3: Verification

**Files:**
- Modify: `tests/gates/phase6_gate.py`

- [ ] **Step 1: Run targeted verification**
- [ ] **Step 2: Run full pytest and phase gates**
