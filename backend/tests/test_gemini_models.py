"""Dynamic Gemini model discovery."""

import httpx

from app.services.llm_config import list_gemini_models


async def test_model_discovery_keeps_chat_models_and_filters_specialized_models(monkeypatch):
    response = {
        "models": [
            {
                "name": "models/gemini-3.5-flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-future-pro",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-3-pro-image",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/gemini-embedding-001",
                "supportedGenerationMethods": ["embedContent"],
            },
        ]
    }
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=response))
    real_client = httpx.AsyncClient

    def factory(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr("app.services.llm_config.httpx.AsyncClient", factory)

    assert await list_gemini_models() == ["gemini-3.5-flash", "gemini-future-pro"]
