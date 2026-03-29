# Stability And Workflow Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the interview-review pipeline, clean up runtime file handling, and add high-value workflow upgrades for reruns and exports.

**Architecture:** Keep the existing Streamlit + service-layer structure, but tighten the runtime contract in `config.py`, centralize rerun/export behavior in `services.analysis_service`, and expose the new workflow from `pages/history.py`. Preserve the current repository-backed storage model and extend it with small, testable helpers instead of broad refactors.

**Tech Stack:** Python, Streamlit, Pydantic, pytest

---

### Task 1: Runtime Paths And Environment Guardrails

**Files:**
- Modify: `config.py`
- Modify: `scripts/self_check.py`
- Modify: `core/runtime.py`
- Modify: `.gitignore`
- Modify: `README.md`
- Test: `tests/test_runtime_workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from config import get_settings
from core.runtime import python_version_status


def test_settings_expose_runtime_upload_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("AUDIO_OUTPUT_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.delenv("UPLOAD_DIR", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    try:
        settings.ensure_runtime_dirs()
        assert settings.runtime_dir == (tmp_path / "runtime").resolve()
        assert settings.upload_dir == (tmp_path / "runtime" / "uploads").resolve()
        assert settings.upload_dir.exists()
    finally:
        get_settings.cache_clear()


def test_python_version_status_warns_for_unvalidated_future_version(monkeypatch) -> None:
    monkeypatch.setattr("core.runtime.sys.version_info", (3, 14, 0))
    status = python_version_status()
    assert status.status == "WARN"
    assert "3.13" in status.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_runtime_workflow.py`
Expected: FAIL because `Settings` does not expose runtime/upload directories and `python_version_status` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class Settings:
    runtime_dir: Path
    upload_dir: Path

    def ensure_runtime_dirs(self) -> None:
        for directory in (self.output_dir, self.audio_output_dir, self.log_dir, self.runtime_dir, self.upload_dir):
            directory.mkdir(parents=True, exist_ok=True)
```

```python
@dataclass(frozen=True)
class PythonVersionStatus:
    status: str
    detail: str


def python_version_status(...) -> PythonVersionStatus:
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_runtime_workflow.py`
Expected: PASS

- [ ] **Step 5: Update docs and ignore rules**

```text
runtime/*
!runtime/.gitkeep
```

Update `README.md` and `scripts/self_check.py` so the documented and reported Python support window matches the runtime helper.

- [ ] **Step 6: Commit**

```bash
git add config.py scripts/self_check.py core/runtime.py .gitignore README.md tests/test_runtime_workflow.py runtime/.gitkeep
git commit -m "fix: harden runtime paths and python support checks"
```

### Task 2: History Export And Rerun Workflow

**Files:**
- Modify: `services/analysis_service.py`
- Modify: `pages/history.py`
- Modify: `ui/analysis_views.py`
- Test: `tests/test_history_workflow.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path

from services.analysis_service import AnalysisService
from services.interview_repo import InterviewRepository


def test_rerun_from_b4_reaches_completed(tmp_path: Path, monkeypatch) -> None:
    ...
    final_status = service.rerun_from_stage(interview_id, "B4")
    assert final_status.current_stage == "B6"
    assert final_status.status.value == "completed"


def test_export_bundle_payload_contains_saved_documents(tmp_path: Path) -> None:
    ...
    payload = service.export_bundle_payload(interview_id)
    assert payload["interview_id"] == interview_id
    assert payload["status"]["current_stage"] == "B6"
    assert "report_markdown" in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_history_workflow.py`
Expected: FAIL because the rerun/export helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class AnalysisService:
    def rerun_from_stage(self, interview_id: str, stage: str, *, status_callback=None) -> StatusDocument:
        ...

    def refresh_artifacts(self, interview_id: str, *, status_callback=None) -> StatusDocument:
        ...

    def export_bundle_payload(self, interview_id: str) -> dict[str, object]:
        ...
```

Expose the new actions in `pages/history.py` with:
- rerun buttons for `B1`, `B4`, and `B6`
- `st.download_button` for report markdown
- `st.download_button` for bundle JSON

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_history_workflow.py`
Expected: PASS

- [ ] **Step 5: Verify the page still renders bundle details**

Run: `.\.venv\Scripts\python.exe -m scripts.run_phase5_gate`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/analysis_service.py pages/history.py ui/analysis_views.py tests/test_history_workflow.py
git commit -m "feat: add history rerun and export workflow"
```

### Task 3: Update New Analysis Upload Storage

**Files:**
- Modify: `pages/new_analysis.py`
- Test: `tests/test_runtime_workflow.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from config import get_settings


def test_uploaded_files_use_runtime_upload_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime"))
    get_settings.cache_clear()
    settings = get_settings()
    try:
        assert settings.upload_dir == (tmp_path / "runtime" / "uploads").resolve()
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_runtime_workflow.py::test_uploaded_files_use_runtime_upload_dir`
Expected: FAIL until `pages/new_analysis.py` stops using `tests/runtime/uploads`.

- [ ] **Step 3: Write minimal implementation**

```python
def _save_uploaded_file(uploaded_file) -> str:
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest -q tests/test_runtime_workflow.py::test_uploaded_files_use_runtime_upload_dir`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pages/new_analysis.py tests/test_runtime_workflow.py
git commit -m "refactor: move uploaded files into runtime workspace"
```

### Task 4: Final Verification

**Files:**
- Modify: `tests/gates/phase5_gate.py`
- Modify: `tests/gates/phase6_gate.py`

- [ ] **Step 1: Align gate fixtures with completed pipeline state where needed**

```python
status = StatusDocument(
    interview_id=interview_id,
    status=PipelineStatus.completed,
    current_stage="B6",
)
status.stages["B6"] = StageStatus.success
```

- [ ] **Step 2: Run focused verification**

Run:
```bash
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.run_phase1_gate
.\.venv\Scripts\python.exe -m scripts.run_phase2_gate
.\.venv\Scripts\python.exe -m scripts.run_phase3_gate
.\.venv\Scripts\python.exe -m scripts.run_phase4_gate
.\.venv\Scripts\python.exe -m scripts.run_phase5_gate
.\.venv\Scripts\python.exe -m scripts.run_phase6_gate
```
Expected: all commands exit 0

- [ ] **Step 3: Commit**

```bash
git add tests/gates/phase5_gate.py tests/gates/phase6_gate.py
git commit -m "test: align gates with completed workflow"
```
