from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from config import get_settings
from core.exceptions import ConfigurationError, ExternalDependencyError
from part_b.schemas import TranscriptSegment, TranscriptionDocument, WordTimestamp

try:
    from qcloud_cos import CosConfig, CosS3Client
except ImportError:  # pragma: no cover - external dependency
    CosConfig = None
    CosS3Client = None

try:
    from tencentcloud.asr.v20190614 import asr_client, models
    from tencentcloud.common import credential
except ImportError:  # pragma: no cover - external dependency
    asr_client = None
    models = None
    credential = None


MAX_INLINE_UPLOAD_BYTES = 5 * 1024 * 1024
DEFAULT_ENGINE_MODEL = "16k_zh"


@dataclass(frozen=True)
class TranscriptionOptions:
    asr_region: str
    engine_model: str
    max_retries: int
    poll_interval_seconds: int
    timeout_seconds: int
    cos_region: str
    cos_bucket: str
    cos_prefix: str
    cos_url_expire_seconds: int


def get_transcription_options() -> TranscriptionOptions:
    settings = get_settings()
    return TranscriptionOptions(
        asr_region=settings.asr_region,
        engine_model=settings.asr_engine_model or DEFAULT_ENGINE_MODEL,
        max_retries=settings.asr_max_retries,
        poll_interval_seconds=settings.asr_poll_interval_seconds,
        timeout_seconds=settings.asr_timeout_seconds,
        cos_region=settings.cos_region,
        cos_bucket=settings.cos_bucket,
        cos_prefix=settings.cos_prefix,
        cos_url_expire_seconds=settings.cos_url_expire_seconds,
    )


def _require_tencent_dependencies() -> None:
    if credential is None or asr_client is None or models is None:
        raise ExternalDependencyError(
            "Tencent Cloud ASR SDK is missing. Please install dependencies from requirements.txt."
        )


def _require_cos_dependencies() -> None:
    if CosConfig is None or CosS3Client is None:
        raise ExternalDependencyError(
            "Tencent Cloud COS SDK is missing. Please install dependencies from requirements.txt."
        )


def _create_asr_client(secret_id: str, secret_key: str, region: str):
    _require_tencent_dependencies()
    cred = credential.Credential(secret_id, secret_key)
    return asr_client.AsrClient(cred, region)


def _response_data(payload: dict) -> dict:
    if isinstance(payload.get("Data"), dict):
        return payload["Data"]
    response = payload.get("Response")
    if isinstance(response, dict) and isinstance(response.get("Data"), dict):
        return response["Data"]
    return {}


def _build_cos_object_key(file_path: Path, prefix: str) -> str:
    cleaned_prefix = prefix.strip("/")
    suffix = file_path.suffix.lower()
    stem = file_path.stem.replace(" ", "_")
    unique = uuid4().hex[:8]
    if cleaned_prefix:
        return f"{cleaned_prefix}/{stem}_{unique}{suffix}"
    return f"{stem}_{unique}{suffix}"


def upload_to_cos(
    file_path: str | Path,
    *,
    secret_id: str,
    secret_key: str,
    region: str,
    bucket: str,
    prefix: str = "asr-input/",
    expire_seconds: int = 3600,
) -> str:
    _require_cos_dependencies()
    if not bucket:
        raise ConfigurationError("COS_BUCKET must be configured for audio files larger than 5MB.")

    source_path = Path(file_path)
    object_key = _build_cos_object_key(source_path, prefix)

    config = CosConfig(
        Region=region,
        SecretId=secret_id,
        SecretKey=secret_key,
        Scheme="https",
    )
    client = CosS3Client(config)
    client.upload_file(
        Bucket=bucket,
        LocalFilePath=str(source_path),
        Key=object_key,
        PartSize=10,
        MAXThread=4,
    )
    return client.get_presigned_download_url(
        Bucket=bucket,
        Key=object_key,
        Expired=expire_seconds,
    )


def _build_create_task_request(
    audio_path: Path,
    *,
    engine_model: str = DEFAULT_ENGINE_MODEL,
    source_url: str | None = None,
):
    request = models.CreateRecTaskRequest()
    request.EngineModelType = engine_model
    request.ChannelNum = 1
    request.ResTextFormat = 2
    request.SpeakerDiarization = 1
    request.SpeakerNumber = 0

    if source_url is not None:
        request.Url = source_url
        request.SourceType = 0
        return request

    raw_bytes = audio_path.read_bytes()
    request.Data = base64.b64encode(raw_bytes).decode()
    request.DataLen = len(raw_bytes)
    request.SourceType = 1
    return request


def _extract_task_id(create_response) -> str:
    payload = json.loads(create_response.to_json_string())
    return str(_response_data(payload)["TaskId"])


def _wait_for_task_result(
    client,
    task_id: str,
    *,
    poll_interval_seconds: int,
    timeout_seconds: int,
) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        request = models.DescribeTaskStatusRequest()
        request.TaskId = int(task_id)
        response = client.DescribeTaskStatus(request)
        payload = json.loads(response.to_json_string())
        data = _response_data(payload)
        status_text = (data.get("StatusStr") or "").lower()

        if status_text == "success":
            return payload
        if status_text == "failed":
            raise RuntimeError(data.get("ErrorMsg") or "Tencent Cloud ASR task failed.")

        time.sleep(poll_interval_seconds)

    raise TimeoutError(f"Tencent Cloud ASR task timed out: {task_id}")


def _word_time_ms(
    sentence_start_ms: int | None,
    *,
    absolute_ms: int | None = None,
    offset_ms: int | None = None,
) -> int | None:
    if absolute_ms is not None:
        return int(absolute_ms)
    if sentence_start_ms is not None and offset_ms is not None:
        return int(sentence_start_ms) + int(offset_ms)
    if offset_ms is not None:
        return int(offset_ms)
    return None


def build_transcription_document(
    interview_id: str,
    audio_path: str | Path,
    raw_response: dict,
    *,
    source_video_path: str | None = None,
) -> TranscriptionDocument:
    data = _response_data(raw_response)
    details = data.get("ResultDetail") or data.get("ResultList") or []
    segments: list[TranscriptSegment] = []
    speakers: set[str] = set()

    for index, item in enumerate(details):
        speaker_id = str(item.get("SpeakerId", "unknown"))
        text = (
            item.get("FinalSentence")
            or item.get("Text")
            or item.get("SliceSentence")
            or item.get("Sentence")
            or ""
        )
        if speaker_id != "unknown":
            speakers.add(speaker_id)

        words = [
            WordTimestamp(
                word=word.get("Word") or word.get("Text") or "",
                start_ms=_word_time_ms(
                    item.get("StartMs"),
                    absolute_ms=word.get("StartMs"),
                    offset_ms=word.get("OffsetStartMs"),
                ),
                end_ms=_word_time_ms(
                    item.get("StartMs"),
                    absolute_ms=word.get("EndMs"),
                    offset_ms=word.get("OffsetEndMs"),
                ),
            )
            for word in (item.get("Words") or [])
        ]

        segments.append(
            TranscriptSegment(
                segment_id=str(item.get("Index") or index),
                speaker_id=speaker_id,
                start_ms=item.get("StartMs"),
                end_ms=item.get("EndMs"),
                text=text,
                words=words,
            )
        )

    if not segments and data.get("Result"):
        segments.append(
            TranscriptSegment(
                segment_id="0",
                speaker_id="unknown",
                text=str(data["Result"]),
            )
        )

    return TranscriptionDocument(
        interview_id=interview_id,
        source_audio_path=str(Path(audio_path).resolve()),
        source_video_path=source_video_path,
        speaker_count=len(speakers) if speakers else None,
        asr_task_id=str(data.get("TaskId")) if data.get("TaskId") is not None else None,
        segments=segments,
        raw_response=raw_response,
    )


def transcribe(
    interview_id: str,
    audio_path: str | Path,
    *,
    secret_id: str,
    secret_key: str,
    options: TranscriptionOptions | None = None,
    source_video_path: str | None = None,
) -> TranscriptionDocument:
    options = options or get_transcription_options()
    source_path = Path(audio_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Audio file does not exist: {source_path}")

    client = _create_asr_client(secret_id, secret_key, options.asr_region)
    source_url = None
    if source_path.stat().st_size > MAX_INLINE_UPLOAD_BYTES:
        if not options.cos_bucket:
            raise ConfigurationError("COS_BUCKET must be configured to submit ASR tasks for audio files larger than 5MB.")
        source_url = upload_to_cos(
            source_path,
            secret_id=secret_id,
            secret_key=secret_key,
            region=options.cos_region,
            bucket=options.cos_bucket,
            prefix=options.cos_prefix,
            expire_seconds=options.cos_url_expire_seconds,
        )

    last_error: Exception | None = None
    for attempt in range(1, options.max_retries + 1):
        try:
            request = _build_create_task_request(
                source_path,
                engine_model=options.engine_model,
                source_url=source_url,
            )
            create_response = client.CreateRecTask(request)
            task_id = _extract_task_id(create_response)
            raw_response = _wait_for_task_result(
                client,
                task_id,
                poll_interval_seconds=options.poll_interval_seconds,
                timeout_seconds=options.timeout_seconds,
            )
            return build_transcription_document(
                interview_id,
                source_path,
                raw_response,
                source_video_path=source_video_path,
            )
        except Exception as exc:  # pragma: no cover - depends on external service
            last_error = exc
            if attempt == options.max_retries:
                break
            time.sleep(attempt * options.poll_interval_seconds)

    raise RuntimeError(f"Tencent Cloud ASR transcription failed: {last_error}") from last_error


def transcribe_with_settings(
    interview_id: str,
    audio_path: str | Path,
    *,
    source_video_path: str | None = None,
) -> TranscriptionDocument:
    settings = get_settings()
    settings.validate(("TENCENT_SECRET_ID", "TENCENT_SECRET_KEY", "ASR_REGION"))
    return transcribe(
        interview_id,
        audio_path,
        secret_id=settings.tencent_secret_id,
        secret_key=settings.tencent_secret_key,
        options=get_transcription_options(),
        source_video_path=source_video_path,
    )
