from __future__ import annotations

from pathlib import Path

from config import get_settings
from core.files import atomic_write_json, atomic_write_text, read_json
from part_b.schemas import GlobalProfileDocument, ResumeProfileDocument


class ProfileService:
    RESUME_FILE = "resume_profile.json"
    GLOBAL_PROFILE_FILE = "global_profile.json"
    GLOBAL_PROFILE_MD_FILE = "global_profile.md"

    def __init__(self, output_root: Path | None = None) -> None:
        settings = get_settings()
        self.output_root = output_root or settings.output_dir
        self.output_root.mkdir(parents=True, exist_ok=True)

    def _path(self, filename: str) -> Path:
        return self.output_root / filename

    def get_resume(self) -> ResumeProfileDocument | None:
        data = read_json(self._path(self.RESUME_FILE))
        return ResumeProfileDocument.model_validate(data) if data else None

    def update_resume(self, data: ResumeProfileDocument | dict) -> ResumeProfileDocument:
        document = (
            data if isinstance(data, ResumeProfileDocument) else ResumeProfileDocument.model_validate(data)
        )
        atomic_write_json(self._path(self.RESUME_FILE), document.model_dump(mode="json"))
        return document

    def delete_resume(self) -> None:
        path = self._path(self.RESUME_FILE)
        if path.exists():
            path.unlink()

    def get_global_profile(self) -> GlobalProfileDocument | None:
        data = read_json(self._path(self.GLOBAL_PROFILE_FILE))
        return GlobalProfileDocument.model_validate(data) if data else None

    def update_global_profile(self, data: GlobalProfileDocument | dict) -> GlobalProfileDocument:
        document = (
            data if isinstance(data, GlobalProfileDocument) else GlobalProfileDocument.model_validate(data)
        )
        atomic_write_json(self._path(self.GLOBAL_PROFILE_FILE), document.model_dump(mode="json"))
        return document

    def get_global_profile_markdown(self) -> str | None:
        path = self._path(self.GLOBAL_PROFILE_MD_FILE)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def update_global_profile_markdown(self, content: str) -> None:
        path = self._path(self.GLOBAL_PROFILE_MD_FILE)
        atomic_write_text(path, content + ("\n" if not content.endswith("\n") else ""))

