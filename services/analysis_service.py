from __future__ import annotations

from pathlib import Path
from typing import Callable
from uuid import uuid4

from config import get_settings
from core.time_utils import utc_now_iso
from part_a.audio_extractor import extract_audio
from part_a.transcriber import transcribe_with_settings
from part_a.validator import validate_input
from part_b.nodes.context_completer import complete_context
from part_b.nodes.qa_pairer import build_qa_pairs
from part_b.nodes.role_identifier import identify_roles
from part_b.nodes.summary_generator import generate_interview_summary
from part_b.nodes.topic_analyzer import analyze_topics
from part_b.reporting import render_report_markdown
from part_b.schemas import (
    DEFAULT_STAGE_ORDER,
    AnalysesDocument,
    CapabilitySnapshotDocument,
    InterviewMetaDocument,
    PipelineStatus,
    QaPairsDocument,
    StageStatus,
    StatusDocument,
    TranscriptionDocument,
)
from services.interview_repo import InterviewBundle, InterviewRepository
from services.capability_service import CapabilityService
from services.profile_service import ProfileService


StatusCallback = Callable[[StatusDocument], None]


class AnalysisService:
    def __init__(self, repository: InterviewRepository | None = None) -> None:
        self.repository = repository or InterviewRepository()
        self.profile_service = ProfileService(output_root=self.repository.output_root)
        self.capability_service = CapabilityService(
            repository=self.repository,
            profile_service=self.profile_service,
        )

    def create_interview_shell(
        self,
        source_file_path: str,
        title: str | None = None,
        input_type: str = "unknown",
    ) -> str:
        source_path = Path(source_file_path)
        interview_id = self._build_interview_id(source_path.stem)
        meta = InterviewMetaDocument(
            interview_id=interview_id,
            title=title or source_path.stem,
            source_file_name=source_path.name,
            source_file_path=str(source_path),
            input_type=input_type if input_type in {"audio", "video", "unknown"} else "unknown",
            file_size_bytes=source_path.stat().st_size if source_path.exists() else None,
        )
        status = StatusDocument(interview_id=interview_id)
        self.repository.save_interview(
            interview_id,
            {
                "meta": meta,
                "status": status,
            },
        )
        return interview_id

    def run_pipeline(
        self,
        audio_path: str,
        status_callback: StatusCallback | None = None,
    ) -> str:
        return self.run_preprocessing(audio_path, status_callback=status_callback)

    def run_preprocessing(
        self,
        input_path: str,
        *,
        title: str | None = None,
        status_callback: StatusCallback | None = None,
    ) -> str:
        settings = get_settings()
        source_path = Path(input_path)
        interview_id = self.create_interview_shell(
            str(source_path),
            title=title or source_path.stem,
            input_type="unknown",
        )

        try:
            self.update_stage(
                interview_id,
                "A1",
                StageStatus.running,
                pipeline_status=PipelineStatus.preprocessing,
                status_callback=status_callback,
            )
            validation = validate_input(
                source_path,
                ffprobe_binary=settings.ffprobe_binary,
            )

            meta = self.repository.load_meta(interview_id)
            if meta is None:
                raise RuntimeError("初始化面试元数据失败。")
            meta.input_type = validation.input_type
            meta.duration_seconds = (
                int(validation.duration_seconds) if validation.duration_seconds is not None else None
            )
            meta.file_size_bytes = validation.size_bytes
            meta.updated_at = utc_now_iso()
            self.repository.save_meta(meta)

            self.update_stage(
                interview_id,
                "A1",
                StageStatus.success,
                pipeline_status=PipelineStatus.preprocessing,
                status_callback=status_callback,
            )

            self.update_stage(
                interview_id,
                "A2",
                StageStatus.running,
                pipeline_status=PipelineStatus.preprocessing,
                status_callback=status_callback,
            )
            extraction = extract_audio(
                source_path,
                settings.audio_output_dir / interview_id,
                ffmpeg_binary=settings.ffmpeg_binary,
            )
            transcription = transcribe_with_settings(
                interview_id,
                extraction.output_path,
                source_video_path=str(source_path) if validation.input_type == "video" else None,
            )
            self.attach_transcription(transcription)
            self.update_stage(
                interview_id,
                "A2",
                StageStatus.success,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )
            return interview_id
        except Exception as exc:
            current_status = self.repository.load_status(interview_id)
            failed_stage = current_status.current_stage if current_status else "A1"
            self.update_stage(
                interview_id,
                failed_stage,
                StageStatus.failed,
                pipeline_status=PipelineStatus.failed,
                error=str(exc),
                status_callback=status_callback,
            )
            raise

    def resume_from(self, interview_id: str, stage: str) -> StatusDocument:
        status = self.repository.load_status(interview_id)
        if status is None:
            raise RuntimeError(f"未找到面试记录: {interview_id}")

        status.current_stage = stage
        status.status = (
            PipelineStatus.preprocessing if stage.startswith("A") else PipelineStatus.analyzing
        )

        reset = False
        for stage_name in DEFAULT_STAGE_ORDER:
            if stage_name == stage:
                reset = True
            if reset:
                status.stages[stage_name] = StageStatus.pending
        status.last_error = None
        status.updated_at = utc_now_iso()
        self.repository.save_status(status)
        return status

    def run_phase3(
        self,
        interview_id: str,
        *,
        status_callback: StatusCallback | None = None,
    ) -> str:
        bundle = self.repository.load_interview(interview_id)
        if bundle.transcription is None:
            raise RuntimeError(f"Missing transcription for interview: {interview_id}")
        if bundle.meta is None:
            raise RuntimeError(f"Missing metadata for interview: {interview_id}")

        resume = self.profile_service.get_resume()

        try:
            self.update_stage(
                interview_id,
                "B1",
                StageStatus.running,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )
            role_result, transcription = identify_roles(
                bundle.transcription,
                meta=bundle.meta,
                resume=resume,
            )
            self.attach_transcription(transcription)
            self.update_stage(
                interview_id,
                "B1",
                StageStatus.success,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )

            self.update_stage(
                interview_id,
                "B2",
                StageStatus.running,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )
            _context_result, meta = complete_context(
                transcription,
                meta=bundle.meta,
                resume=resume,
                role_result=role_result,
            )
            meta.updated_at = utc_now_iso()
            self.repository.save_meta(meta)
            self.update_stage(
                interview_id,
                "B2",
                StageStatus.success,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )

            self.update_stage(
                interview_id,
                "B3",
                StageStatus.running,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )
            qa_pairs = build_qa_pairs(
                transcription,
                meta=meta,
            )
            self.attach_qa_pairs(qa_pairs)
            self.update_stage(
                interview_id,
                "B3",
                StageStatus.success,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )
            return interview_id
        except Exception as exc:
            current_status = self.repository.load_status(interview_id)
            failed_stage = current_status.current_stage if current_status else "B1"
            self.update_stage(
                interview_id,
                failed_stage,
                StageStatus.failed,
                pipeline_status=PipelineStatus.failed,
                error=str(exc),
                status_callback=status_callback,
            )
            raise

    def run_phase4(
        self,
        interview_id: str,
        *,
        status_callback: StatusCallback | None = None,
    ) -> str:
        bundle = self.repository.load_interview(interview_id)
        if bundle.meta is None:
            raise RuntimeError(f"Missing metadata for interview: {interview_id}")
        if bundle.qa_pairs is None:
            raise RuntimeError(f"Missing qa_pairs for interview: {interview_id}")

        resume = self.profile_service.get_resume()

        try:
            self.update_stage(
                interview_id,
                "B4",
                StageStatus.running,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )
            analyses = analyze_topics(
                bundle.qa_pairs,
                meta=bundle.meta,
                resume=resume,
            )
            analyses.summary = generate_interview_summary(
                analyses.analyses,
                meta=bundle.meta,
                resume=resume,
            )
            analyses.updated_at = utc_now_iso()
            self.attach_analyses(analyses)
            self.update_stage(
                interview_id,
                "B4",
                StageStatus.success,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )

            self.update_stage(
                interview_id,
                "B5",
                StageStatus.running,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )
            report_markdown = render_report_markdown(
                meta=bundle.meta,
                analyses=analyses,
            )
            self.attach_report(interview_id, report_markdown)
            self.capability_service.ensure_artifacts(interview_id)
            self.update_stage(
                interview_id,
                "B5",
                StageStatus.success,
                pipeline_status=PipelineStatus.analyzing,
                status_callback=status_callback,
            )
            return interview_id
        except Exception as exc:
            current_status = self.repository.load_status(interview_id)
            failed_stage = current_status.current_stage if current_status else "B4"
            self.update_stage(
                interview_id,
                failed_stage,
                StageStatus.failed,
                pipeline_status=PipelineStatus.failed,
                error=str(exc),
                status_callback=status_callback,
            )
            raise

    def update_stage(
        self,
        interview_id: str,
        stage: str,
        stage_status: StageStatus,
        *,
        pipeline_status: PipelineStatus | None = None,
        error: str | None = None,
        status_callback: StatusCallback | None = None,
    ) -> StatusDocument:
        status = self.repository.load_status(interview_id)
        if status is None:
            raise RuntimeError(f"未找到面试记录: {interview_id}")

        status.current_stage = stage
        status.stages[stage] = stage_status
        status.last_error = error
        if pipeline_status is not None:
            status.status = pipeline_status
        elif stage_status == StageStatus.failed:
            status.status = PipelineStatus.failed
        elif stage_status == StageStatus.success and stage == DEFAULT_STAGE_ORDER[-1]:
            status.status = PipelineStatus.completed
        status.updated_at = utc_now_iso()
        self.repository.save_status(status)

        if status_callback:
            status_callback(status)
        return status

    def attach_transcription(self, document: TranscriptionDocument) -> None:
        self.repository.save_transcription(document)

    def attach_qa_pairs(self, document: QaPairsDocument) -> None:
        self.repository.save_qa_pairs(document)

    def attach_analyses(self, document: AnalysesDocument) -> None:
        self.repository.save_analyses(document)

    def attach_capability_snapshot(self, document: CapabilitySnapshotDocument) -> None:
        self.repository.save_capability_snapshot(document)

    def attach_report(self, interview_id: str, markdown: str) -> None:
        self.repository.save_report(interview_id, markdown)

    def load_bundle(self, interview_id: str) -> InterviewBundle:
        return self.repository.load_interview(interview_id)

    def list_interviews(self) -> list:
        return self.repository.list_all()

    def _build_interview_id(self, label: str) -> str:
        safe_label = label.replace(" ", "_").replace("/", "_").replace("\\", "_")
        return f"{utc_now_iso()[:10]}_{safe_label}_{uuid4().hex[:8]}"
