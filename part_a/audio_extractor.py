from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.exceptions import ExternalDependencyError
from core.runtime import command_path


TARGET_AUDIO_SUFFIX = ".mp3"
TARGET_SAMPLE_RATE = "16000"
TARGET_CHANNELS = "1"
TARGET_BITRATE = "64k"


@dataclass(frozen=True)
class AudioExtractionResult:
    source_path: Path
    output_path: Path
    reused_source: bool
    command: list[str]


def build_ffmpeg_audio_command(
    input_path: str | Path,
    output_path: str | Path,
    ffmpeg_binary: str = "ffmpeg",
) -> list[str]:
    return [
        ffmpeg_binary,
        "-i",
        str(Path(input_path)),
        "-vn",
        "-ar",
        TARGET_SAMPLE_RATE,
        "-ac",
        TARGET_CHANNELS,
        "-b:a",
        TARGET_BITRATE,
        "-y",
        str(Path(output_path)),
    ]


def extract_audio(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
) -> AudioExtractionResult:
    source_path = Path(input_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    resolved_ffmpeg = command_path(ffmpeg_binary)
    if resolved_ffmpeg is None:
        raise ExternalDependencyError(
            f"FFmpeg binary '{ffmpeg_binary}' not found. Please install FFmpeg and ensure it is in PATH."
        )

    if source_path.suffix.lower() == TARGET_AUDIO_SUFFIX:
        return AudioExtractionResult(
            source_path=source_path.resolve(),
            output_path=source_path.resolve(),
            reused_source=True,
            command=[],
        )

    output_path = target_dir / f"{source_path.stem}{TARGET_AUDIO_SUFFIX}"
    command = build_ffmpeg_audio_command(
        source_path,
        output_path,
        ffmpeg_binary=resolved_ffmpeg,
    )
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "FFmpeg execution failed"
        raise RuntimeError(f"FFmpeg audio extraction failed: {detail}")

    return AudioExtractionResult(
        source_path=source_path.resolve(),
        output_path=output_path.resolve(),
        reused_source=False,
        command=command,
    )
