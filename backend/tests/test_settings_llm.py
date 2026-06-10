"""Per-user LLM settings: defaults, persistence, isolation, key masking."""
from app.services.llm_config import resolve_llm_config, save_llm_config

NEW_CONFIG = {
    "base_url": "https://my-llm.example/v1",
    "api_key": "sk-user-a-secret-1234",
    "model": "my-model",
}


async def test_get_returns_env_defaults_when_unset(client, sales_headers):
    resp = await client.get("/api/settings/llm", headers=sales_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_url"] == "https://llm.test/v1"
    assert body["model"] == "env-default-model"
    # Key is never returned in clear text.
    assert body["api_key_masked"].startswith("***")
    assert "env-default-key" not in body["api_key_masked"]


async def test_put_then_get_roundtrip(client, sales_headers):
    resp = await client.put("/api/settings/llm", json=NEW_CONFIG, headers=sales_headers)
    assert resp.status_code == 200

    resp = await client.get("/api/settings/llm", headers=sales_headers)
    body = resp.json()
    assert body["base_url"] == NEW_CONFIG["base_url"]
    assert body["model"] == NEW_CONFIG["model"]
    assert body["api_key_masked"] == "***1234"


async def test_settings_are_isolated_per_user(client, sales_headers, other_sales_headers):
    await client.put("/api/settings/llm", json=NEW_CONFIG, headers=sales_headers)

    resp = await client.get("/api/settings/llm", headers=other_sales_headers)
    body = resp.json()
    # The second user still sees env defaults, not user A's config.
    assert body["base_url"] == "https://llm.test/v1"
    assert body["model"] == "env-default-model"


async def test_blank_api_key_keeps_existing_key(client, sales_headers):
    await client.put("/api/settings/llm", json=NEW_CONFIG, headers=sales_headers)

    resp = await client.put(
        "/api/settings/llm",
        json={"base_url": "https://changed.example/v1", "api_key": "  ", "model": "other-model"},
        headers=sales_headers,
    )
    assert resp.status_code == 200

    resp = await client.get("/api/settings/llm", headers=sales_headers)
    body = resp.json()
    assert body["base_url"] == "https://changed.example/v1"
    assert body["model"] == "other-model"
    assert body["api_key_masked"] == "***1234"  # unchanged


async def test_sales_role_can_manage_own_llm_settings(client, sales_headers):
    # Previously manager-only; per-user settings are open to every role.
    resp = await client.get("/api/settings/llm", headers=sales_headers)
    assert resp.status_code == 200


async def test_llm_settings_require_auth(client):
    resp = await client.get("/api/settings/llm")
    assert resp.status_code == 401


async def test_resolve_llm_config_prefers_user_rows(db_session, sales_user, other_sales_user):
    await save_llm_config(
        db_session,
        sales_user.id,
        base_url="https://a.example/v1",
        api_key="key-a",
        model="model-a",
    )
    await db_session.commit()

    cfg_a = await resolve_llm_config(db_session, sales_user.id)
    assert (cfg_a.base_url, cfg_a.api_key, cfg_a.model) == (
        "https://a.example/v1",
        "key-a",
        "model-a",
    )

    cfg_b = await resolve_llm_config(db_session, other_sales_user.id)
    assert cfg_b.base_url == "https://llm.test/v1"
    assert cfg_b.api_key == "env-default-key"
    assert cfg_b.model == "env-default-model"
