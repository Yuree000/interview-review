from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from core.exceptions import ConfigurationError

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

ENV_TO_FIELD = {
    "TENCENT_SECRET_ID": "tencent_secret_id",
    "TENCENT_SECRET_KEY": "tencent_secret_key",
    "ASR_REGION": "asr_region",
    "ASR_ENGINE_MODEL": "asr_engine_model",
    "ASR_MAX_RETRIES": "asr_max_retries",
    "ASR_POLL_INTERVAL_SECONDS": "asr_poll_interval_seconds",
    "ASR_TIMEOUT_SECONDS": "asr_timeout_seconds",
    "COS_REGION": "cos_region",
    "COS_BUCKET": "cos_bucket",
    "COS_PREFIX": "cos_prefix",
    "COS_URL_EXPIRE_SECONDS": "cos_url_expire_seconds",
    "LLM_API_KEY": "llm_api_key",
    "LLM_BASE_URL": "llm_base_url",
    "LLM_MODEL": "llm_model",
    "LLM_STRUCTURED_MODEL": "llm_structured_model",
}


def load_project_env() -> None:
    if load_dotenv and ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name, str(default)).lower()
    return value in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got: {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    debug: bool
    base_dir: Path
    output_dir: Path
    audio_output_dir: Path
    log_dir: Path
    ffmpeg_binary: str
    ffprobe_binary: str
    tencent_secret_id: str
    tencent_secret_key: str
    asr_region: str
    asr_engine_model: str
    asr_max_retries: int
    asr_poll_interval_seconds: int
    asr_timeout_seconds: int
    cos_region: str
    cos_bucket: str
    cos_prefix: str
    cos_url_expire_seconds: int
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_structured_model: str

    def ensure_runtime_dirs(self) -> None:
        for directory in (self.output_dir, self.audio_output_dir, self.log_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def missing_keys(self, keys: Iterable[str]) -> list[str]:
        missing: list[str] = []
        for key in keys:
            field_name = ENV_TO_FIELD.get(key)
            if field_name is None:
                raise ConfigurationError(f"Unknown configuration key: {key}")
            value = getattr(self, field_name)
            if value in ("", None):
                missing.append(key)
        return missing

    def validate(self, keys: Iterable[str]) -> None:
        missing = self.missing_keys(keys)
        if missing:
            missing_text = ", ".join(missing)
            guidance = (
                f"Please set these variables in {ENV_FILE.name}."
                if ENV_FILE.exists()
                else f"Please copy .env.example to {ENV_FILE.name} and set these variables."
            )
            raise ConfigurationError(
                f"Missing required configuration: {missing_text}. {guidance}"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_project_env()

    output_dir = (BASE_DIR / _env("OUTPUT_DIR", "./outputs")).resolve()
    audio_output_dir = (BASE_DIR / _env("AUDIO_OUTPUT_DIR", "./audio_cache")).resolve()
    log_dir = (BASE_DIR / _env("LOG_DIR", "./logs")).resolve()

    return Settings(
        app_name="Interview Review System",
        app_env=_env("APP_ENV", "development"),
        debug=_env_bool("APP_DEBUG", True),
        base_dir=BASE_DIR,
        output_dir=output_dir,
        audio_output_dir=audio_output_dir,
        log_dir=log_dir,
        ffmpeg_binary=_env("FFMPEG_BINARY", "ffmpeg"),
        ffprobe_binary=_env("FFPROBE_BINARY", "ffprobe"),
        tencent_secret_id=_env("TENCENT_SECRET_ID"),
        tencent_secret_key=_env("TENCENT_SECRET_KEY"),
        asr_region=_env("ASR_REGION", "ap-guangzhou"),
        asr_engine_model=_env("ASR_ENGINE_MODEL", "16k_zh"),
        asr_max_retries=_env_int("ASR_MAX_RETRIES", 3),
        asr_poll_interval_seconds=_env_int("ASR_POLL_INTERVAL_SECONDS", 5),
        asr_timeout_seconds=_env_int("ASR_TIMEOUT_SECONDS", 1800),
        cos_region=_env("COS_REGION", "ap-guangzhou"),
        cos_bucket=_env("COS_BUCKET"),
        cos_prefix=_env("COS_PREFIX", "asr-input/"),
        cos_url_expire_seconds=_env_int("COS_URL_EXPIRE_SECONDS", 3600),
        llm_api_key=_env("LLM_API_KEY"),
        llm_base_url=_env("LLM_BASE_URL", "https://api.moonshot.cn/v1"),
        llm_model=_env("LLM_MODEL", "kimi-k2.5"),
        llm_structured_model=_env("LLM_STRUCTURED_MODEL", "moonshot-v1-128k"),
    )
