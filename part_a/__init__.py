"""Part A: input validation, audio extraction and transcription."""

from part_a.audio_extractor import AudioExtractionResult, extract_audio
from part_a.transcriber import (
    TranscriptionOptions,
    build_transcription_document,
    transcribe,
    transcribe_with_settings,
    upload_to_cos,
)
from part_a.validator import (
    AUDIO_FORMATS,
    SUPPORTED_FORMATS,
    VIDEO_FORMATS,
    InputValidationResult,
    classify_input_type,
    probe_duration_seconds,
    validate_input,
)

__all__ = [
    "AUDIO_FORMATS",
    "AudioExtractionResult",
    "InputValidationResult",
    "SUPPORTED_FORMATS",
    "TranscriptionOptions",
    "VIDEO_FORMATS",
    "build_transcription_document",
    "classify_input_type",
    "extract_audio",
    "probe_duration_seconds",
    "transcribe",
    "transcribe_with_settings",
    "upload_to_cos",
    "validate_input",
]
