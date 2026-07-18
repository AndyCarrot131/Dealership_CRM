"""Gemini-compatible request construction and truncation handling."""

import json

import httpx
import pytest

from app.llm.client import LLMClient
from app.services.llm_config import LLMRuntimeConfig


CONFIG = LLMRuntimeConfig(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    api_key="test-key",
    model="gemini-3.5-flash",
)


def _patch_http(monkeypatch, response: dict) -> list[dict]:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=response)

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def factory(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr("app.llm.client.httpx.AsyncClient", factory)
    return requests


async def test_chat_sends_gemini_reasoning_and_json_options(monkeypatch):
    requests = _patch_http(
        monkeypatch,
        {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]},
    )
    client = LLMClient(CONFIG, log_requests=False)

    await client.chat(
        [{"role": "user", "content": "extract"}],
        max_tokens=16384,
        reasoning_effort="low",
        response_format={"type": "json_object"},
        chat_template_kwargs={"enable_thinking": False},
    )

    assert requests[0]["max_tokens"] == 16384
    assert requests[0]["reasoning_effort"] == "low"
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert "chat_template_kwargs" not in requests[0]


async def test_chat_reports_truncated_response(monkeypatch):
    _patch_http(
        monkeypatch,
        {"choices": [{"finish_reason": "length", "message": {"content": "{\"x\":"}}]},
    )
    client = LLMClient(CONFIG, log_requests=False)

    with pytest.raises(RuntimeError, match="exhausted its output token budget"):
        await client.chat([{"role": "user", "content": "extract"}])
