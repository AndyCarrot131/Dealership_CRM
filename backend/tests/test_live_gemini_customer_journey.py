"""Focused live Gemini Flash acceptance tests.

Each test exercises one AI capability so a quota or provider failure can be
rerun without repeating the entire sales journey::

    pytest -m live_gemini tests/test_live_gemini_customer_journey.py -v
"""

import asyncio
from pathlib import Path

import pytest

from app.api import deals as deals_api
from app.config import settings
from app.llm import GEMINI_API_KEY_REF, GEMINI_BASE_URL, GEMINI_MODEL
from app.llm.client import LLMClient, get_llm_client
from app.main import app
from app.models.llm_profile import LLMProfile
from app.services.llm_config import resolve_llm_config


pytestmark = pytest.mark.live_gemini
TEST_FILES = Path(__file__).resolve().parents[2] / "test_files"


def _assert_ok(response, expected=200):
    assert response.status_code == expected, response.text
    return response.json() if response.content else None


async def _post_with_backoff(client, url, **kwargs):
    response = None
    for delay in (0, 10, 20, 40):
        if delay:
            await asyncio.sleep(delay)
        response = await client.post(url, **kwargs)
        if response.status_code != 503:
            return response
    return response


@pytest.fixture
async def live_gemini(db_session, sales_user, tmp_path, monkeypatch):
    if not settings.gemini_api_key or settings.gemini_api_key == "env-default-key":
        pytest.skip("A real GEMINI_API_KEY is required")
    db_session.add(
        LLMProfile(
            user_id=sales_user.id,
            name="Gemini Flash live acceptance",
            base_url=GEMINI_BASE_URL,
            api_key=GEMINI_API_KEY_REF,
            model=GEMINI_MODEL,
            is_active=True,
            is_system=True,
        )
    )
    await db_session.commit()
    config = await resolve_llm_config(db_session, sales_user.id)
    assert "flash" in config.model.lower()
    client = LLMClient(config, log_requests=False)
    app.dependency_overrides[get_llm_client] = lambda: client
    app.dependency_overrides[deals_api._llm_for_extract] = lambda: client
    monkeypatch.setattr(deals_api.settings, "uploads_dir", str(tmp_path))
    return client


async def test_live_gemini_parses_contact_notes(
    client, sales_headers, live_gemini
):
    result = _assert_ok(
        await _post_with_backoff(
            client,
            "/api/interactions/parse",
            headers=sales_headers,
            json={
                "raw_text": (
                    "On July 17, 2026 I called Fixture Customer. They want a black "
                    "Volkswagen Tiguan with heated seats and will visit at 10 AM."
                )
            },
        )
    )
    assert result["channel"] == "call"
    assert "Tiguan" in result["summary"]


@pytest.mark.parametrize(
    ("image_name", "expected_year", "expected_type"),
    (("test_deal1.jpg", 2020, "finance"), ("test_deal2.jpg", 2022, "lease")),
)
async def test_live_gemini_extracts_one_deal_image(
    client,
    sales_headers,
    live_gemini,
    image_name,
    expected_year,
    expected_type,
):
    path = TEST_FILES / image_name
    result = _assert_ok(
        await _post_with_backoff(
            client,
            "/api/deals/extract",
            headers=sales_headers,
            files={"file": (image_name, path.read_bytes(), "image/jpeg")},
        )
    )["extracted"]
    assert result["model_year"] == expected_year
    assert result["make"].lower() == "volkswagen"
    assert "tiguan" in result["model"].lower()
    assert result["deal_type"] == expected_type


async def test_live_gemini_summarizes_style_and_writes_inventory_email(
    client, sales_headers, live_gemini
):
    for filename, label in (
        ("test_drive.txt", "test drive follow-up"),
        ("lease_email.txt", "lease maturity"),
    ):
        _assert_ok(
            await client.post(
                "/api/style/samples",
                headers=sales_headers,
                json={
                    "channel": "email",
                    "raw_content": (TEST_FILES / filename).read_text(encoding="utf-8"),
                    "label": label,
                },
            ),
            201,
        )
    style = _assert_ok(
        await _post_with_backoff(
            client, "/api/style/summarize/email", headers=sales_headers
        )
    )["style_md"]
    assert len(style) >= 80

    from app.agents.email_composer import compose_email

    draft = await compose_email(
        customer={
            "full_name": "Fixture Customer",
            "cars": [{"make": "Volkswagen", "model": "Tiguan", "year": 2022}],
            "interactions": [],
        },
        inventory_matches=[
            {
                "make": "Volkswagen",
                "model": "Tiguan",
                "year": 2026,
                "trim": "Highline R-Line",
                "price": 44995,
            }
        ],
        style_md=style,
        llm=live_gemini,
        email_type="test_drive_followup",
    )
    assert draft["subject"]
    assert "Tiguan" in draft["body"]


async def test_live_gemini_builds_support_and_inventory_briefing(
    client, sales_headers, live_gemini
):
    customer = _assert_ok(
        await client.post(
            "/api/customers",
            headers=sales_headers,
            json={"full_name": "Fixture Customer"},
        ),
        201,
    )
    customer_id = customer["id"]
    _assert_ok(
        await client.post(
            f"/api/customers/{customer_id}/cars",
            headers=sales_headers,
            json={"make": "Volkswagen", "model": "Tiguan", "year": 2022},
        ),
        201,
    )
    inventory = _assert_ok(
        await client.post(
            "/api/inventory",
            headers=sales_headers,
            json={
                "make": "Volkswagen",
                "model": "Tiguan",
                "year": 2026,
                "trim": "Highline R-Line",
                "status": "available",
            },
        ),
        201,
    )
    _assert_ok(
        await client.post(
            "/api/support-docs",
            headers=sales_headers,
            json={
                "category": "appointment",
                "title": "Tiguan replacement preparation",
                "content": "Prepare an available matching Tiguan for the visit.",
                "checks": (
                    "Trigger when the customer owns a 2022 Tiguan and matching "
                    "available inventory is present."
                ),
                "effective_from": "2026-01-01",
                "effective_to": None,
            },
        ),
        201,
    )
    briefing = _assert_ok(
        await _post_with_backoff(
            client, f"/api/customers/{customer_id}/briefing", headers=sales_headers
        )
    )
    assert briefing["triggered_count"] == 1
    assert briefing["summary"]
    assert any(item["id"] == inventory["id"] for item in briefing["inventory"])
