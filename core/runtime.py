from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


def _binary_fallbacks(command_name: str) -> list[Path]:
    home = Path.home()
    local_app_data = Path(os.getenv("LOCALAPPDATA", ""))
    normalized = Path(command_name).name.lower()

    fallbacks: dict[str, list[Path]] = {
        "ffmpeg": [
            home / ".local" / "ffmpeg" / "bin" / "ffmpeg.exe",
            local_app_data / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
        ],
        "ffprobe": [
            home / ".local" / "ffmpeg" / "bin" / "ffprobe.exe",
            local_app_data / "Microsoft" / "WinGet" / "Links" / "ffprobe.exe",
        ],
    }
    return fallbacks.get(normalized, [])


def command_path(command_name: str) -> str | None:
    direct_path = Path(command_name).expanduser()
    if direct_path.is_file():
        return str(direct_path.resolve())

    resolved = shutil.which(command_name)
    if resolved:
        return resolved

    for candidate in _binary_fallbacks(command_name):
        if candidate.is_file():
            return str(candidate.resolve())
    return None


@dataclass(frozen=True)
class PythonVersionStatus:
    status: str
    detail: str


def python_version_supported(
    min_major: int = 3,
    min_minor: int = 11,
    *,
    max_major: int | None = None,
    max_minor: int | None = None,
    version_info: tuple[int, ...] | None = None,
) -> bool:
    current = version_info or sys.version_info
    version_pair = (current[0], current[1])
    if version_pair < (min_major, min_minor):
        return False
    if max_major is not None and max_minor is not None and version_pair > (max_major, max_minor):
        return False
    return True


def python_version_status(
    *,
    version_info: tuple[int, ...] | None = None,
    min_major: int = 3,
    min_minor: int = 11,
    validated_max_major: int = 3,
    validated_max_minor: int = 13,
) -> PythonVersionStatus:
    current = version_info or sys.version_info
    version_text = f"{current[0]}.{current[1]}.{current[2] if len(current) > 2 else 0}"
    validated_range = f"{min_major}.{min_minor}-{validated_max_major}.{validated_max_minor}"

    if not python_version_supported(
        min_major,
        min_minor,
        version_info=current,
    ):
        return PythonVersionStatus(
            status="FAIL",
            detail=f"{version_text} (requires Python {min_major}.{min_minor}+)",
        )

    if not python_version_supported(
        min_major,
        min_minor,
        max_major=validated_max_major,
        max_minor=validated_max_minor,
        version_info=current,
    ):
        return PythonVersionStatus(
            status="WARN",
            detail=f"{version_text} (validated for Python {validated_range}; newer versions may emit dependency warnings)",
        )

    return PythonVersionStatus(status="PASS", detail=version_text)
