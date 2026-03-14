from __future__ import annotations

from pathlib import Path
from shutil import rmtree

from part_a.audio_extractor import AudioExtractionResult, TARGET_BITRATE, build_ffmpeg_audio_command
from part_a.transcriber import build_transcription_document
from part_a.validator import InputValidationResult, max_file_size_gb_for_extension, validate_input
from services.analysis_service import AnalysisService
from services.interview_repo import InterviewRepository


def run_phase2_gate() -> list[tuple[str, str, str]]:
    root = Path(__file__).resolve().parents[1] / "runtime" / "phase2"
    if root.exists():
        rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    valid_audio = root / "demo.mp3"
    valid_audio.write_bytes(b"fake-audio")
    invalid_file = root / "demo.txt"
    invalid_file.write_text("bad", encoding="utf-8")

    results: list[tuple[str, str, str]] = []

    def check(name: str, fn) -> None:
        try:
            fn()
        except Exception as exc:  # pragma: no cover
            results.append((name, "FAIL", f"{type(exc).__name__}: {exc}"))
        else:
            results.append((name, "PASS", "ok"))

    def validate_supported_input() -> None:
        result = validate_input(valid_audio, ffprobe_binary="__missing_ffprobe__")
        assert result.extension == ".mp3"
        assert result.input_type == "audio"

    def reject_unsupported_input() -> None:
        try:
            validate_input(invalid_file, ffprobe_binary="__missing_ffprobe__")
        except ValueError:
            return
        raise AssertionError("Unsupported format should be rejected")

    def mp4_size_limit_rule() -> None:
        assert max_file_size_gb_for_extension(".mp4") == 20
        assert max_file_size_gb_for_extension(".mp3") == 1

    def ffmpeg_command_shape() -> None:
        command = build_ffmpeg_audio_command("in.mp4", "out.mp3")
        assert command[0] == "ffmpeg"
        assert "-vn" in command
        assert TARGET_BITRATE in command

    def parse_transcription_payload() -> None:
        raw_response = {
            "Data": {
                "TaskId": 123,
                "ResultDetail": [
                    {
                        "Index": 0,
                        "SpeakerId": 0,
                        "FinalSentence": "请介绍一下微服务经验",
                        "StartMs": 1000,
                        "EndMs": 2200,
                        "Words": [
                            {
                                "Word": "请介绍",
                                "OffsetStartMs": 0,
                                "OffsetEndMs": 200,
                            }
                        ],
                    }
                ],
            }
        }
        document = build_transcription_document("demo", valid_audio, raw_response)
        assert document.asr_task_id == "123"
        assert len(document.segments) == 1
        assert document.speaker_count == 1
        assert document.segments[0].words[0].start_ms == 1000
        assert document.segments[0].words[0].end_ms == 1200

    def analysis_service_preprocessing_flow() -> None:
        from services import analysis_service as analysis_module

        fake_input = root / "demo.mp4"
        fake_input.write_bytes(b"fake-video")
        fake_audio_dir = root / "audio"
        fake_audio_dir.mkdir(parents=True, exist_ok=True)
        fake_audio = fake_audio_dir / "demo.mp3"
        fake_audio.write_bytes(b"fake-audio")

        repository = InterviewRepository(output_root=root / "analysis_repo")
        service = AnalysisService(repository=repository)

        original_validate = analysis_module.validate_input
        original_extract = analysis_module.extract_audio
        original_transcribe = analysis_module.transcribe_with_settings

        def fake_validate(*args, **kwargs):
            return InputValidationResult(
                source_path=fake_input.resolve(),
                extension=".mp4",
                input_type="video",
                size_bytes=fake_input.stat().st_size,
                size_gb=0.0,
                duration_seconds=12.0,
            )

        def fake_extract(*args, **kwargs):
            return AudioExtractionResult(
                source_path=fake_input.resolve(),
                output_path=fake_audio.resolve(),
                reused_source=False,
                command=["ffmpeg"],
            )

        def fake_transcribe(interview_id: str, audio_path, *, source_video_path=None):
            raw_response = {
                "Data": {
                    "TaskId": 456,
                    "ResultDetail": [
                        {
                            "Index": 0,
                            "SpeakerId": 0,
                            "FinalSentence": "你好",
                        }
                    ],
                }
            }
            return build_transcription_document(
                interview_id,
                audio_path,
                raw_response,
                source_video_path=source_video_path,
            )

        analysis_module.validate_input = fake_validate
        analysis_module.extract_audio = fake_extract
        analysis_module.transcribe_with_settings = fake_transcribe
        try:
            interview_id = service.run_preprocessing(str(fake_input))
            bundle = repository.load_interview(interview_id)
            assert bundle.status is not None
            assert bundle.status.stages["A1"].value == "success"
            assert bundle.status.stages["A2"].value == "success"
            assert bundle.transcription is not None
            assert bundle.meta is not None
            assert bundle.meta.input_type == "video"
        finally:
            analysis_module.validate_input = original_validate
            analysis_module.extract_audio = original_extract
            analysis_module.transcribe_with_settings = original_transcribe

    check("validate_supported_input", validate_supported_input)
    check("reject_unsupported_input", reject_unsupported_input)
    check("mp4_size_limit_rule", mp4_size_limit_rule)
    check("ffmpeg_command_shape", ffmpeg_command_shape)
    check("parse_transcription_payload", parse_transcription_payload)
    check("analysis_service_preprocessing_flow", analysis_service_preprocessing_flow)
    return results
