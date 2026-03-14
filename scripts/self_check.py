from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from config import ENV_FILE, get_settings
from core.exceptions import ConfigurationError
from core.logging_config import configure_logging
from core.runtime import command_path, python_version_supported


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def _status_line(result: CheckResult) -> str:
    return f"[{result.status}] {result.name}: {result.detail}"


def run_checks(required_keys: list[str]) -> list[CheckResult]:
    settings = get_settings()
    settings.ensure_runtime_dirs()
    configure_logging(settings.log_dir, debug=settings.debug)

    results = [
        CheckResult(
            "Python >= 3.10",
            "PASS" if python_version_supported() else "FAIL",
            sys.version.split()[0],
        ),
        CheckResult(
            ".env.example",
            "PASS" if (settings.base_dir / ".env.example").exists() else "FAIL",
            "Exists" if (settings.base_dir / ".env.example").exists() else "Missing",
        ),
        CheckResult(
            "requirements.txt",
            "PASS" if (settings.base_dir / "requirements.txt").exists() else "FAIL",
            "Exists" if (settings.base_dir / "requirements.txt").exists() else "Missing",
        ),
        CheckResult(
            ".env",
            "PASS" if ENV_FILE.exists() else "WARN",
            "Exists" if ENV_FILE.exists() else "Not created, needed before external service integration",
        ),
    ]

    ffmpeg_path = command_path(settings.ffmpeg_binary)
    results.append(
        CheckResult(
            "FFmpeg",
            "PASS" if ffmpeg_path else "WARN",
            ffmpeg_path or "Not detected, install and add to PATH before Phase 2",
        )
    )

    ffprobe_path = command_path(settings.ffprobe_binary)
    results.append(
        CheckResult(
            "FFprobe",
            "PASS" if ffprobe_path else "WARN",
            ffprobe_path or "Not detected, duration probing will be skipped",
        )
    )

    cos_sdk_installed = importlib.util.find_spec("qcloud_cos") is not None
    results.append(
        CheckResult(
            "COS Python SDK",
            "PASS" if cos_sdk_installed else "WARN",
            "Installed" if cos_sdk_installed else "Not installed, run: pip install -r requirements.txt",
        )
    )

    asr_sdk_installed = importlib.util.find_spec("tencentcloud") is not None
    results.append(
        CheckResult(
            "Tencent ASR SDK",
            "PASS" if asr_sdk_installed else "WARN",
            "Installed" if asr_sdk_installed else "Not installed, run: pip install -r requirements.txt",
        )
    )

    if required_keys:
        try:
            settings.validate(required_keys)
        except ConfigurationError as exc:
            results.append(CheckResult("Configuration validation", "FAIL", str(exc)))
        else:
            results.append(CheckResult("Configuration validation", "PASS", "All required keys present"))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Project self-check")
    parser.add_argument(
        "--require",
        nargs="*",
        default=[],
        help="Additional required environment variables, e.g., --require TENCENT_SECRET_ID TENCENT_SECRET_KEY",
    )
    args = parser.parse_args()

    results = run_checks(args.require)
    for result in results:
        print(_status_line(result))

    has_failure = any(result.status == "FAIL" for result in results)
    return 1 if has_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
