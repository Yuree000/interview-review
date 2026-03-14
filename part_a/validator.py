from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.exceptions import ExternalDependencyError
from core.runtime import command_path


SUPPORTED_FORMATS = {
    ".mp4",
    ".mp3",
    ".wav",
    ".m4a",
    ".flv",
    ".wma",
    ".aac",
    ".flac",
}
VIDEO_FORMATS = {".mp4", ".flv"}
AUDIO_FORMATS = SUPPORTED_FORMATS - VIDEO_FORMATS
MAX_DURATION_HOURS = 5
MAX_DEFAULT_FILE_SIZE_GB = 1
MAX_MP4_FILE_SIZE_GB = 20


@dataclass(frozen=True)
class InputValidationResult:
    source_path: Path
    extension: str
    input_type: str
    size_bytes: int
    size_gb: float
    duration_seconds: float | None


def max_file_size_gb_for_extension(extension: str, default_limit_gb: int = MAX_DEFAULT_FILE_SIZE_GB) -> int:
    if extension == ".mp4":
        return MAX_MP4_FILE_SIZE_GB
    return default_limit_gb


def classify_input_type(path: str | Path) -> str:
    extension = Path(path).suffix.lower()
    if extension in VIDEO_FORMATS:
        return "video"
    if extension in AUDIO_FORMATS:
        return "audio"
    return "unknown"


def probe_duration_seconds(path: str | Path, ffprobe_binary: str = "ffprobe") -> float | None:
    resolved = command_path(ffprobe_binary)
    if resolved is None:
        return None

    source_path = Path(path)
    command = [
        resolved,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(source_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "ffprobe execution failed")

    output = result.stdout.strip()
    if not output:
        return None
    return float(output)


def validate_input(
    path: str | Path,
    *,
    ffprobe_binary: str = "ffprobe",
    max_duration_hours: int = MAX_DURATION_HOURS,
    max_file_size_gb: int | None = None,
    require_duration: bool = False,
) -> InputValidationResult:
    source_path = Path(path)
    if not source_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {source_path}")
    if not source_path.is_file():
        raise ValueError(f"Input path is not a file: {source_path}")

    extension = source_path.suffix.lower()
    if extension not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {extension}")

    size_bytes = source_path.stat().st_size
    size_gb = size_bytes / (1024**3)
    effective_size_limit_gb = (
        max_file_size_gb
        if max_file_size_gb is not None
        else max_file_size_gb_for_extension(extension)
    )
    if size_gb > effective_size_limit_gb:
        raise ValueError(f"File too large: {size_gb:.2f}GB > {effective_size_limit_gb}GB")

    duration_seconds = probe_duration_seconds(source_path, ffprobe_binary=ffprobe_binary)
    if duration_seconds is None and require_duration:
        raise ExternalDependencyError(
            f"Unable to probe duration. Please ensure {ffprobe_binary} is installed and in PATH."
        )
    if duration_seconds is not None and duration_seconds > max_duration_hours * 3600:
        raise ValueError(
            f"Duration too long: {duration_seconds / 3600:.2f}h > {max_duration_hours}h"
        )

    return InputValidationResult(
        source_path=source_path.resolve(),
        extension=extension,
        input_type=classify_input_type(source_path),
        size_bytes=size_bytes,
        size_gb=size_gb,
        duration_seconds=duration_seconds,
    )
