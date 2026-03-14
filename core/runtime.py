from __future__ import annotations

import os
import shutil
import sys
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


def python_version_supported(min_major: int = 3, min_minor: int = 10) -> bool:
    return sys.version_info >= (min_major, min_minor)
