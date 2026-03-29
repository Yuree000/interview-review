from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def format_timestamp_ms(value_ms: int | None) -> str:
    if value_ms is None:
        return ""
    total_seconds = max(0, value_ms // 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_ms_range(start_ms: int | None, end_ms: int | None) -> str:
    start_text = format_timestamp_ms(start_ms)
    end_text = format_timestamp_ms(end_ms)
    if start_text and end_text:
        return f"{start_text} - {end_text}"
    return start_text or end_text or "--:--"
