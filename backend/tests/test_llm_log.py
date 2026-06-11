"""Tests for LLM request logging (training-data collection)."""
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.llm.client import LLMClient
from app.models.llm_log import LLMRequestLog
from app.services.llm_config import LLMRuntimeConfig
from app.services.llm_log import record_llm_request

CONFIG = LLMRuntimeConfig(
    base_url="https://llm.test/v1",
    api_key="test-key",
    model="test-model",
)

CHAT_RESPONSE = {
    "choices": [{"message": {"role": "assistant", "content": "Hello there"}}]
}


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


def _patch_llm_http(monkeypatch, handler) -> None:
    """Route LLMClient's internal httpx.AsyncClient through a mock transport."""
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def factory(**kwargs):
        kwargs["transport"] = transport
        return real_async_client(**kwargs)

    monkeypatch.setattr("app.llm.client.httpx.AsyncClient", factory)


async def _fetch_logs(session_factory) -> list[LLMRequestLog]:
    async with session_factory() as session:
        result = await session.execute(select(LLMRequestLog))
        return list(result.scalars())


async def test_record_llm_request_writes_row(session_factory):
    await record_llm_request(
        session_factory,
        url="https://llm.test/v1/chat/completions",
        model="test-model",
        request_payload={"messages": [{"role": "user", "content": "hi"}]},
        response_payload=CHAT_RESPONSE,
    )

    logs = await _fetch_logs(session_factory)
    assert len(logs) == 1
    assert logs[0].url == "https://llm.test/v1/chat/completions"
    assert logs[0].model == "test-model"
    assert logs[0].input["messages"][0]["content"] == "hi"
    assert logs[0].output == CHAT_RESPONSE
    assert logs[0].created_at is not None


async def test_chat_success_records_url_model_input_output(
    monkeypatch, session_factory
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CHAT_RESPONSE)

    _patch_llm_http(monkeypatch, handler)
    client = LLMClient(CONFIG, session_factory=session_factory)

    messages = [{"role": "user", "content": "list my customers"}]
    tools = [{"type": "function", "function": {"name": "query_db"}}]
    data = await client.chat(messages, tools=tools)

    assert data == CHAT_RESPONSE
    logs = await _fetch_logs(session_factory)
    assert len(logs) == 1
    log = logs[0]
    assert log.url == "https://llm.test/v1/chat/completions"
    assert log.model == "test-model"
    assert log.input["messages"] == messages
    assert log.input["tools"] == tools
    assert log.output == CHAT_RESPONSE


async def test_failed_request_is_not_logged(monkeypatch, session_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    _patch_llm_http(monkeypatch, handler)
    client = LLMClient(CONFIG, session_factory=session_factory)

    with pytest.raises(httpx.HTTPStatusError):
        await client.chat([{"role": "user", "content": "hi"}])

    assert await _fetch_logs(session_factory) == []


async def test_logging_failure_does_not_break_chat(monkeypatch, session_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CHAT_RESPONSE)

    _patch_llm_http(monkeypatch, handler)

    def broken_session_factory():
        raise RuntimeError("db down")

    client = LLMClient(CONFIG, session_factory=broken_session_factory)
    data = await client.chat([{"role": "user", "content": "hi"}])

    assert data == CHAT_RESPONSE
