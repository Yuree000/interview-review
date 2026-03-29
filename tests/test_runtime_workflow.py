from __future__ import annotations

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


def test_python_version_status_warns_for_unvalidated_future_version() -> None:
    status = python_version_status(version_info=(3, 14, 0))

    assert status.status == "WARN"
    assert "3.11-3.13" in status.detail
