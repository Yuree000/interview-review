from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from config import get_settings
from core.exceptions import ConfigurationError


T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=1)
def get_llm_client() -> OpenAI:
    settings = get_settings()
    if not settings.llm_api_key:
        raise ConfigurationError("LLM_API_KEY is required before running Part B.")
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )


def llm_available() -> bool:
    settings = get_settings()
    return bool(settings.llm_api_key and settings.llm_model and settings.llm_base_url)


def _extract_json_payload(text: str) -> dict:
    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced_match:
        return json.loads(fenced_match.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(text[start : end + 1])


def _is_temperature_restriction_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "invalid temperature" in message and "only 1 is allowed" in message


def invoke_json_model(
    response_model: type[T],
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    retries: int = 3,
    model_name: str | None = None,
    json_mode: bool = False,
) -> T:
    settings = get_settings()
    client = get_llm_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    model = model_name or settings.llm_model

    last_error: Exception | None = None
    for _ in range(retries):
        try:
            request_kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode:
                request_kwargs["response_format"] = {"type": "json_object"}
            try:
                response = client.chat.completions.create(**request_kwargs)
            except Exception as exc:
                if not _is_temperature_restriction_error(exc):
                    raise
                request_kwargs["temperature"] = 1
                response = client.chat.completions.create(**request_kwargs)
            content = response.choices[0].message.content or ""
            payload = _extract_json_payload(content)
            return response_model.model_validate(payload)
        except Exception as exc:
            last_error = exc

    raise RuntimeError(f"LLM structured response failed: {last_error}") from last_error


def safe_invoke_json_model(
    response_model: type[T],
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    retries: int = 3,
    model_name: str | None = None,
    json_mode: bool = False,
) -> T | None:
    if not llm_available():
        return None
    try:
        return invoke_json_model(
            response_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            retries=retries,
            model_name=model_name,
            json_mode=json_mode,
        )
    except Exception:
        return None
