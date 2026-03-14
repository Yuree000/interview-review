from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from config import get_settings
from core.files import atomic_write_json, atomic_write_text, ensure_dir, read_json
from part_b.schemas import (
    AnalysesDocument,
    CapabilitySnapshotDocument,
    InterviewMetaDocument,
    QaPairsDocument,
    StatusDocument,
    TranscriptionDocument,
)


@dataclass
class InterviewBundle:
    interview_id: str
    status: StatusDocument | None
    meta: InterviewMetaDocument | None
    transcription: TranscriptionDocument | None
    qa_pairs: QaPairsDocument | None
    analyses: AnalysesDocument | None
    capability_snapshot: CapabilitySnapshotDocument | None
    report_markdown: str | None


@dataclass
class InterviewListItem:
    interview_id: str
    status: str | None
    current_stage: str | None
    title: str | None
    target_position: str | None
    created_at: str | None
    updated_at: str | None


class InterviewRepository:
    STATUS_FILE = "status.json"
    META_FILE = "meta.json"
    TRANSCRIPTION_FILE = "transcription.json"
    QA_PAIRS_FILE = "qa_pairs.json"
    ANALYSES_FILE = "analyses.json"
    SNAPSHOT_FILE = "capability_snapshot.json"
    REPORT_FILE = "report.md"

    def __init__(self, output_root: Path | None = None) -> None:
        settings = get_settings()
        self.output_root = output_root or settings.output_dir
        ensure_dir(self.output_root)

    def get_interview_dir(self, interview_id: str) -> Path:
        return self.output_root / interview_id

    def ensure_interview_dir(self, interview_id: str) -> Path:
        return ensure_dir(self.get_interview_dir(interview_id))

    def _json_path(self, interview_id: str, filename: str) -> Path:
        return self.get_interview_dir(interview_id) / filename

    def _save_model(self, interview_id: str, filename: str, model: BaseModel) -> None:
        self.ensure_interview_dir(interview_id)
        atomic_write_json(
            self._json_path(interview_id, filename),
            model.model_dump(mode="json"),
        )

    def _load_model(self, interview_id: str, filename: str, model_cls: type[BaseModel]) -> BaseModel | None:
        path = self._json_path(interview_id, filename)
        data = read_json(path)
        if data is None:
            return None
        return model_cls.model_validate(data)

    def save_status(self, document: StatusDocument) -> None:
        self._save_model(document.interview_id, self.STATUS_FILE, document)

    def load_status(self, interview_id: str) -> StatusDocument | None:
        return self._load_model(interview_id, self.STATUS_FILE, StatusDocument)

    def save_meta(self, document: InterviewMetaDocument) -> None:
        self._save_model(document.interview_id, self.META_FILE, document)

    def load_meta(self, interview_id: str) -> InterviewMetaDocument | None:
        return self._load_model(interview_id, self.META_FILE, InterviewMetaDocument)

    def save_transcription(self, document: TranscriptionDocument) -> None:
        self._save_model(document.interview_id, self.TRANSCRIPTION_FILE, document)

    def load_transcription(self, interview_id: str) -> TranscriptionDocument | None:
        return self._load_model(interview_id, self.TRANSCRIPTION_FILE, TranscriptionDocument)

    def save_qa_pairs(self, document: QaPairsDocument) -> None:
        self._save_model(document.interview_id, self.QA_PAIRS_FILE, document)

    def load_qa_pairs(self, interview_id: str) -> QaPairsDocument | None:
        return self._load_model(interview_id, self.QA_PAIRS_FILE, QaPairsDocument)

    def save_analyses(self, document: AnalysesDocument) -> None:
        self._save_model(document.interview_id, self.ANALYSES_FILE, document)

    def load_analyses(self, interview_id: str) -> AnalysesDocument | None:
        return self._load_model(interview_id, self.ANALYSES_FILE, AnalysesDocument)

    def save_capability_snapshot(self, document: CapabilitySnapshotDocument) -> None:
        self._save_model(document.interview_id, self.SNAPSHOT_FILE, document)

    def load_capability_snapshot(self, interview_id: str) -> CapabilitySnapshotDocument | None:
        return self._load_model(interview_id, self.SNAPSHOT_FILE, CapabilitySnapshotDocument)

    def save_report(self, interview_id: str, markdown: str) -> None:
        self.ensure_interview_dir(interview_id)
        atomic_write_text(self._json_path(interview_id, self.REPORT_FILE), markdown + ("\n" if not markdown.endswith("\n") else ""))

    def load_report(self, interview_id: str) -> str | None:
        path = self._json_path(interview_id, self.REPORT_FILE)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def save_interview(self, interview_id: str, data: dict[str, Any]) -> None:
        if "status" in data and isinstance(data["status"], StatusDocument):
            self.save_status(data["status"])
        if "meta" in data and isinstance(data["meta"], InterviewMetaDocument):
            self.save_meta(data["meta"])
        if "transcription" in data and isinstance(data["transcription"], TranscriptionDocument):
            self.save_transcription(data["transcription"])
        if "qa_pairs" in data and isinstance(data["qa_pairs"], QaPairsDocument):
            self.save_qa_pairs(data["qa_pairs"])
        if "analyses" in data and isinstance(data["analyses"], AnalysesDocument):
            self.save_analyses(data["analyses"])
        if "capability_snapshot" in data and isinstance(data["capability_snapshot"], CapabilitySnapshotDocument):
            self.save_capability_snapshot(data["capability_snapshot"])
        if "report_markdown" in data and isinstance(data["report_markdown"], str):
            self.save_report(interview_id, data["report_markdown"])

    def load_interview(self, interview_id: str) -> InterviewBundle:
        return InterviewBundle(
            interview_id=interview_id,
            status=self.load_status(interview_id),
            meta=self.load_meta(interview_id),
            transcription=self.load_transcription(interview_id),
            qa_pairs=self.load_qa_pairs(interview_id),
            analyses=self.load_analyses(interview_id),
            capability_snapshot=self.load_capability_snapshot(interview_id),
            report_markdown=self.load_report(interview_id),
        )

    def list_all(self, filters: dict[str, Any] | None = None) -> list[InterviewListItem]:
        filters = filters or {}
        records: list[InterviewListItem] = []
        for path in sorted(self.output_root.iterdir(), reverse=True):
            if not path.is_dir():
                continue
            interview_id = path.name
            meta = self.load_meta(interview_id)
            status = self.load_status(interview_id)
            item = InterviewListItem(
                interview_id=interview_id,
                status=status.status.value if status else None,
                current_stage=status.current_stage if status else None,
                title=meta.title if meta else interview_id,
                target_position=meta.target_position if meta else None,
                created_at=meta.created_at if meta else None,
                updated_at=status.updated_at if status else None,
            )
            if not self._match_filters(item, filters):
                continue
            records.append(item)
        return records

    def delete(self, interview_id: str) -> None:
        target = self.get_interview_dir(interview_id)
        if target.exists():
            shutil.rmtree(target)

    def _match_filters(self, item: InterviewListItem, filters: dict[str, Any]) -> bool:
        for key, expected in filters.items():
            if expected in (None, "", []):
                continue
            actual = getattr(item, key, None)
            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

