from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from core.exceptions import ProjectError
from part_b.schemas import ResumeProfileDocument, ResumeProject
from services.profile_service import ProfileService


KNOWN_TECH = [
    "Python",
    "Java",
    "Spring Boot",
    "Spring",
    "MySQL",
    "PostgreSQL",
    "Redis",
    "Kafka",
    "RabbitMQ",
    "Vue",
    "React",
    "TypeScript",
    "JavaScript",
    "Go",
    "Docker",
    "Kubernetes",
    "LLM",
]

POSITION_HINTS = [
    "Backend Engineer",
    "Backend Developer",
    "Java Backend Engineer",
    "Frontend Engineer",
    "Frontend Developer",
    "Full Stack Engineer",
    "Data Engineer",
    "AI Engineer",
    "Algorithm Engineer",
    "QA Engineer",
]

PROJECT_SPLIT_HINTS = ("项目经历", "项目经验", "项目名称", "工作经历", "实习经历")


@dataclass
class ResumeIngestResult:
    profile: ResumeProfileDocument
    raw_text: str
    source_path: str | None = None


class ResumeIngestService:
    def __init__(self, profile_service: ProfileService | None = None) -> None:
        self.profile_service = profile_service or ProfileService()

    def ingest_file(self, file_path: str | Path) -> ResumeIngestResult:
        path = Path(file_path)
        if not path.exists():
            raise ProjectError(f"Resume file not found: {path}")
        raw_text = extract_text_from_resume(path)
        profile = build_resume_profile(raw_text)
        stored = self.profile_service.update_resume(profile)
        return ResumeIngestResult(profile=stored, raw_text=raw_text, source_path=str(path))

    def ingest_text(self, raw_text: str) -> ResumeIngestResult:
        profile = build_resume_profile(raw_text)
        stored = self.profile_service.update_resume(profile)
        return ResumeIngestResult(profile=stored, raw_text=raw_text)

    def ingest_bytes(self, filename: str, content: bytes) -> ResumeIngestResult:
        safe_name = Path(filename).name or "resume.txt"
        temp_dir = self.profile_service.output_root / "_imports" / "resume"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f"{uuid4().hex}_{safe_name}"
        temp_path.write_bytes(content)
        try:
            raw_text = extract_text_from_resume(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)
        profile = build_resume_profile(raw_text)
        stored = self.profile_service.update_resume(profile)
        return ResumeIngestResult(profile=stored, raw_text=raw_text, source_path=safe_name)


def extract_text_from_resume(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".docx":
        return _extract_docx_text(path)
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    raise ProjectError(f"Unsupported resume format: {suffix}")


def build_resume_profile(raw_text: str) -> ResumeProfileDocument:
    cleaned = _normalize_text(raw_text)
    return ResumeProfileDocument(
        name=_guess_name(cleaned),
        target_positions=_guess_target_positions(cleaned),
        years_of_experience=_guess_years(cleaned),
        tech_stack=_guess_tech_stack(cleaned),
        education=_guess_education(cleaned),
        key_projects=_guess_projects(cleaned),
        raw_text=cleaned,
    )


def _extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        try:
            xml_bytes = archive.read("word/document.xml")
        except KeyError as exc:
            raise ProjectError(f"Invalid DOCX structure: {path}") from exc
    root = ElementTree.fromstring(xml_bytes)
    texts = [node.text for node in root.iter() if node.text]
    return "\n".join(texts)


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ProjectError("Reading PDF resumes requires `pypdf` to be installed.") from exc

    reader = PdfReader(str(path))
    texts = [page.extract_text() or "" for page in reader.pages]
    combined = "\n".join(texts).strip()
    if not combined:
        raise ProjectError("PDF resume does not contain extractable text.")
    return combined


def _normalize_text(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.replace("\r", "\n").split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _guess_name(text: str) -> str | None:
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if 1 <= len(first_line) <= 20 and not any(char.isdigit() for char in first_line):
        return first_line
    match = re.search(r"(姓名|Name)[:：]?\s*([A-Za-z\u4e00-\u9fff·]{2,20})", text, flags=re.IGNORECASE)
    return match.group(2).strip() if match else None


def _guess_target_positions(text: str) -> list[str]:
    hits = [position for position in POSITION_HINTS if position.lower() in text.lower()]
    if hits:
        return hits[:3]
    if "后端" in text:
        return ["Backend Engineer"]
    if "前端" in text:
        return ["Frontend Engineer"]
    if "算法" in text or "AI" in text or "机器学习" in text:
        return ["AI Engineer"]
    return []


def _guess_years(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(年|years?)", text, flags=re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _guess_tech_stack(text: str) -> list[str]:
    lower_text = text.lower()
    techs = [tech for tech in KNOWN_TECH if tech.lower() in lower_text]
    return techs[:12]


def _guess_education(text: str) -> str | None:
    for line in text.splitlines():
        if any(keyword in line for keyword in ("大学", "学院", "硕士", "本科", "博士", "Bachelor", "Master", "PhD")):
            return line
    return None


def _guess_projects(text: str) -> list[ResumeProject]:
    lines = text.splitlines()
    projects: list[ResumeProject] = []
    collecting = False
    for line in lines:
        if any(hint in line for hint in PROJECT_SPLIT_HINTS):
            collecting = True
            continue
        if not collecting:
            continue
        if len(projects) >= 3:
            break
        if len(line) < 4:
            continue
        if any(keyword in line for keyword in ("负责", "实现", "优化", "设计", "搭建")):
            if projects:
                projects[-1].highlights.append(line)
            continue
        if len(line) <= 40:
            projects.append(ResumeProject(name=line))
    return projects
