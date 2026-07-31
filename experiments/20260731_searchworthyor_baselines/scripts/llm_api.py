from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMConfig:
    model: str
    reasoning_effort: str
    base_url: str
    api_key: str
    timeout_seconds: int = 300
    temperature: float = 0.0

    @classmethod
    def from_environment(
        cls,
        model: str = "gpt-5.6",
        reasoning_effort: str = "high",
    ) -> "LLMConfig":
        api_key = os.environ.get("OPENOR_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENOR_BASE_URL") or os.environ.get(
            "OPENAI_BASE_URL"
        )
        if not api_key:
            raise RuntimeError("Missing OPENOR_API_KEY or OPENAI_API_KEY.")
        if not base_url:
            raise RuntimeError("Missing OPENOR_BASE_URL or OPENAI_BASE_URL.")
        normalized = base_url.rstrip("/")
        if not normalized.endswith("/v1"):
            normalized += "/v1"
        return cls(
            model=model,
            reasoning_effort=reasoning_effort,
            base_url=normalized,
            api_key=api_key,
        )


class StrictReasoningClient:
    """OpenAI-compatible client that never silently drops reasoning_effort."""

    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "reasoning_effort": self.config.reasoning_effort,
            "temperature": self.config.temperature,
        }
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(
                request, timeout=self.config.timeout_seconds
            ) as response:
                raw = response.read()
                request_id = response.headers.get("x-request-id")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"LLM HTTP {exc.code}; reasoning_effort was not downgraded: {body[:1000]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM transport error: {exc}") from exc
        elapsed = time.perf_counter() - started
        parsed = json.loads(raw.decode("utf-8"))
        choices = parsed.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response contained no choices.")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(
                "LLM returned empty content; strict high-reasoning run is invalid."
            )
        actual_model = parsed.get("model")
        return {
            "content": content,
            "requested_model": self.config.model,
            "actual_model": actual_model,
            "requested_reasoning_effort": self.config.reasoning_effort,
            "reasoning_fallback": False,
            "usage": parsed.get("usage") or {},
            "request_id": request_id,
            "elapsed_seconds": elapsed,
        }
