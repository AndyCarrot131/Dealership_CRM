"""Gemini defaults, optional cloud profiles, and key masking."""

from app.models.llm_profile import LLMProfile
from app.services.llm_config import resolve_llm_config


async def test_get_returns_gemini_defaults_when_unset(client, sales_headers):
    resp = await client.get("/api/settings/llm", headers=sales_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert body["model"] == "gemini-3.5-flash"
    assert body["api_key_masked"].startswith("***")
    assert "env-default-key" not in body["api_key_masked"]


async def test_llm_settings_require_auth(client):
    resp = await client.get("/api/settings/llm")
    assert resp.status_code == 401


async def test_resolve_llm_config_prefers_active_cloud_profile(db_session, sales_user):
    profile = LLMProfile(
        user_id=sales_user.id,
        name="Cloud override",
        base_url="https://cloud.example/v1",
        api_key="cloud-key",
        model="cloud-model",
        is_active=True,
    )
    db_session.add(profile)
    await db_session.commit()

    cfg = await resolve_llm_config(db_session, sales_user.id)
    assert (cfg.base_url, cfg.api_key, cfg.model) == (
        "https://cloud.example/v1",
        "cloud-key",
        "cloud-model",
    )
