"""Deals: vision extraction endpoint, confirm-save (match-or-create), scoping, cascade."""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.api import deals as deals_api
from app.agents.deal_extractor import _clean, _parse_json_content, _to_date, _to_number
from app.config import settings
from app.main import app
from app.models.customer import Customer, CustomerCar
from app.models.deal import Deal, DealLineItem, DealTrade
from app.models.llm_profile import LLMProfile
from app.services.deal_dates import compute_contract_end_date
from sqlalchemy import select


# ─── contract end date ──────────────────────────────────────────────────────────


def test_compute_contract_end_date_lease():
    end = compute_contract_end_date(
        "lease", date(2022, 6, 12), term=48,
    )
    assert end == date(2026, 6, 12)


def test_compute_contract_end_date_finance_uses_num_payments_fallback():
    end = compute_contract_end_date(
        "finance", date(2022, 11, 4), num_payments=72,
    )
    assert end == date(2028, 11, 4)


def test_compute_contract_end_date_cash_is_none():
    assert compute_contract_end_date("cash", date(2022, 1, 1), term=48) is None


# ─── extractor unit tests ───────────────────────────────────────────────────────


def test_to_number_handles_contract_formats():
    assert _to_number("42,340.00") == 42340.0
    assert _to_number("(300.00)") == -300.0
    assert _to_number("($221.70)") == -221.7
    assert _to_number("-700") == -700.0
    assert _to_number(394.12) == 394.12
    assert _to_number("") is None
    assert _to_number("n/a") is None


def test_to_date_accepts_printed_formats():
    assert _to_date("09/16/2022") == "2022-09-16"
    assert _to_date("2022-09-16") == "2022-09-16"
    assert _to_date("garbage") is None


def test_parse_json_content_reads_first_object_only():
    text = (
        '{"deal_type": "lease", "customer": {"name": "Briana", "phone": "902-555-0100"}}\n'
        '{"ignored": "second object"}'
    )
    parsed = _parse_json_content(text)
    assert parsed["deal_type"] == "lease"
    assert parsed["customer"]["phone"] == "902-555-0100"


def test_parse_json_content_ignores_trailing_prose():
    parsed = _parse_json_content('{"deal_type": "cash"}\nDone.')
    assert parsed["deal_type"] == "cash"


def test_clean_preserves_zero_rate_and_nulls_missing_rate():
    cleaned = _clean({"deal_type": "finance", "rate_pct": 0, "term": "72"})
    assert cleaned["rate_pct"] == 0.0  # 0% promo rate must NOT become None
    assert cleaned["term"] == 72

    cleaned = _clean({"deal_type": "finance"})
    assert cleaned["rate_pct"] is None


def test_clean_nulls_lease_fields_for_non_lease():
    cleaned = _clean(
        {"deal_type": "finance", "residual_pct": 47, "km_per_year": 20000, "buy_option_price": 1}
    )
    assert cleaned["residual_pct"] is None
    assert cleaned["km_per_year"] is None
    assert cleaned["buy_option_price"] is None


def test_clean_customer_accepts_flat_and_dealer_form_keys():
    cleaned = _clean(
        {
            "deal_type": "lease",
            "customer": {"name": "Briana C."},
            "phone": "(902) 225-9368",
            "email": "brialgee@gmail.com",
        }
    )
    assert cleaned["customer"] == {
        "name": "Briana C.",
        "phone": "(902) 225-9368",
        "email": "brialgee@gmail.com",
    }

    cleaned = _clean(
        {
            "deal_type": "lease",
            "customer": {
                "name": "Briana C.",
                "cell": "(902) 225-9368",
                "email_address": "brialgee@gmail.com",
            },
        }
    )
    assert cleaned["customer"]["phone"] == "(902) 225-9368"
    assert cleaned["customer"]["email"] == "brialgee@gmail.com"


def test_clean_line_items_and_trades():
    cleaned = _clean(
        {
            "deal_type": "finance",
            "line_items": [
                {"item_name": "Air Tax", "category": "gov_levy", "amount": "100.00"},
                {"item_name": "Discount in lieu of PPM", "category": "bogus", "amount": "(700)"},
                {"item_name": None, "amount": "10"},  # dropped: no name
            ],
            "trades": [
                {"make": "Volkswagen", "model": "Jetta Sedan", "model_year": "2015",
                 "allocation": "8,650.00", "lien_payout": "0.00"},
            ],
            "payment_frequency": "Bi-Weekly",
        }
    )
    assert cleaned["line_items"] == [
        {"item_name": "Air Tax", "category": "gov_levy", "amount": 100.0},
        {"item_name": "Discount in lieu of PPM", "category": "discount", "amount": -700.0},
    ]
    assert cleaned["trades"][0]["allocation"] == 8650.0
    assert cleaned["payment_frequency"] == "biweekly"


def test_clean_lifts_lease_terms_from_nested_block():
    cleaned = _clean(
        {
            "deal_type": "lease",
            "lease": {
                "lender": "VW Credit Canada Inc.",
                "rate": "5.99",
                "term": 48,
                "payment_frequency": "Bi-Weekly",
                "number_of_payments": 104,
                "base_pmt": "$220.25",
                "payment": "$253.29",
                "kpy_allowed": "20,000",
                "residual_percent": 47,
                "residual_value": "18,983.30",
            },
            "make": "Volkswagen",
            "model": "Tiguan",
            "model_year": 2022,
            "selling_price": "42,340.00",
        }
    )
    assert cleaned["deal_type"] == "lease"
    assert cleaned["lender"] == "VW Credit Canada Inc."
    assert cleaned["rate_pct"] == 5.99
    assert cleaned["term"] == 48
    assert cleaned["payment_frequency"] == "biweekly"
    assert cleaned["num_payments"] == 104
    assert cleaned["base_payment"] == 220.25
    assert cleaned["payment_amount"] == 253.29
    assert cleaned["km_per_year"] == 20000
    assert cleaned["residual_pct"] == 47.0
    assert cleaned["residual_value"] == 18983.30


def test_clean_infers_lease_type_from_km_per_year_alias():
    cleaned = _clean(
        {
            "km_y_allowed": 20000,
            "rate": 5.99,
            "term": 48,
            "make": "Volkswagen",
            "model": "Tiguan",
            "model_year": 2022,
            "selling_price": "42340",
        }
    )
    assert cleaned["deal_type"] == "lease"
    assert cleaned["km_per_year"] == 20000


def test_clean_maps_vehicle_aliases():
    cleaned = _clean(
        {
            "deal_type": "lease",
            "vehicle_vin": "3VV8B7AX3NM140605",
            "stock": "VW00767",
            "odometer": "56,486",
            "make": "Volkswagen",
            "model": "Tiguan",
            "model_year": 2022,
            "selling_price": "42340",
        }
    )
    assert cleaned["vin"] == "3VV8B7AX3NM140605"
    assert cleaned["stock_number"] == "VW00767"
    assert cleaned["odometer_at_deal"] == 56486


def test_clean_reconciles_duplicated_term_and_monthly_hallucination():
    """Model often copies term->num_payments and computes payment as price/term."""
    cleaned = _clean(
        {
            "deal_type": "lease",
            "term": 36,
            "num_payments": 36,
            "payment_frequency": "monthly",
            "payment_amount": 1211.27,
            "selling_price": 43600,
            "number_of_payments": 104,
            "payment": 253.29,
            "rate_pct": 5.99,
            "lender": "VW Credit Canada Inc.",
            "km_per_year": 20000,
            "residual_pct": 0.47,
        }
    )
    assert cleaned["term"] == 48
    assert cleaned["num_payments"] == 104
    assert cleaned["payment_frequency"] == "biweekly"
    assert cleaned["payment_amount"] == 253.29
    assert cleaned["residual_pct"] == 47.0


def test_clean_rejects_price_divided_by_term_payment():
    cleaned = _clean(
        {
            "deal_type": "finance",
            "term": 36,
            "num_payments": 36,
            "payment_frequency": "monthly",
            "payment_amount": 1211.11,
            "selling_price": 43600,
            "payment": 394.12,
        }
    )
    assert cleaned["payment_amount"] == 394.12


def test_clean_fixes_semimonthly_combo_when_raw_has_biweekly_lease():
    cleaned = _clean(
        {
            "deal_type": "lease",
            "term": 36,
            "num_payments": 72,
            "payment_frequency": "semimonthly",
            "payment_amount": 1150,
            "selling_price": 43600,
            "capital_cost": 44119.45,
            "lease": {
                "term": 48,
                "number_of_payments": 104,
                "payment_frequency": "Bi-Weekly",
                "payment": 253.29,
                "base_pmt": 220.25,
                "residual_percent": 47,
                "km_y_allowed": 20000,
            },
        }
    )
    assert cleaned["term"] == 48
    assert cleaned["num_payments"] == 104
    assert cleaned["payment_frequency"] == "biweekly"
    assert cleaned["payment_amount"] == 253.29
    assert cleaned["base_payment"] == 220.25
    assert cleaned["residual_pct"] == 47.0
    assert cleaned["km_per_year"] == 20000


def test_clean_fixes_equal_base_and_total_hallucination():
    """Model often sets base_payment == payment_amount (639.99) instead of 220.25 / 253.29."""
    cleaned = _clean(
        {
            "deal_type": "lease",
            "term": 48,
            "num_payments": 104,
            "payment_frequency": "biweekly",
            "rate_pct": 5.99,
            "payment_amount": 639.99,
            "base_payment": 639.99,
            "selling_price": 44100,
            "capital_cost": 38999,
            "payment": 253.29,
            "base_pmt": 220.25,
            "lender": "VW Credit Canada Inc.",
            "km_per_year": 20000,
            "residual_pct": 47,
            "residual_value": 18983.30,
        }
    )
    assert cleaned["payment_amount"] == 253.29
    assert cleaned["base_payment"] == 220.25
    assert cleaned["payment_frequency"] == "biweekly"
    assert cleaned["num_payments"] == 104


def test_clean_rejects_high_biweekly_payment_without_alternatives():
    """When no correct pair exists in raw JSON, flag implausible bi-weekly amount."""
    cleaned = _clean(
        {
            "deal_type": "lease",
            "term": 48,
            "num_payments": 104,
            "payment_frequency": "biweekly",
            "payment_amount": 639.99,
            "base_payment": 639.99,
            "selling_price": 44100,
            "capital_cost": 38999,
        }
    )
    # Without alternate values, implausible amounts are cleared rather than kept wrong.
    assert cleaned["term"] == 48
    assert cleaned["num_payments"] == 104
    assert cleaned["payment_frequency"] == "biweekly"
    assert cleaned["payment_amount"] is None
    assert cleaned["base_payment"] is None


def test_clean_reconciles_pricing_from_nested_block():
    """Model invents round placeholders; nested pricing block has correct O'Regan rows."""
    cleaned = _clean(
        {
            "deal_type": "lease",
            "selling_price": 45600,
            "capital_cost": 38715,
            "cash_down": 1000,
            "cap_reduction": 1000,
            "drive_off_total": 40715,
            "discount": -1500,
            "fees_total": 2500,
            "term": 48,
            "num_payments": 104,
            "payment_frequency": "biweekly",
            "payment_amount": 253.29,
            "base_payment": 220.25,
            "pricing": {
                "selling_price": "42,340.00",
                "sub_total": "44,119.45",
                "capital_cost": "44,119.45",
                "cash_down": "8,781.75",
                "cap_reduction": "8,781.75",
                "drive_off_total": "11,000.00",
                "discount": "(250.00)",
                "net_lease": "35,337.70",
                "line_items": [
                    {"item_name": "Air Tax", "category": "gov_levy", "amount": "100.00"},
                    {"item_name": "Admin Fee", "category": "admin", "amount": "499.00"},
                ],
            },
        }
    )
    assert cleaned["selling_price"] == 42340.0
    assert cleaned["capital_cost"] == 44119.45
    assert cleaned["cash_down"] == 8781.75
    assert cleaned["cap_reduction"] == 8781.75
    assert cleaned["drive_off_total"] == 11000.0
    assert cleaned["discount"] == -250.0


def test_clean_rejects_placeholder_pricing_without_alternatives():
    cleaned = _clean(
        {
            "deal_type": "lease",
            "selling_price": 45600,
            "capital_cost": 38715,
            "cash_down": 1000,
            "drive_off_total": 40715,
            "fees_total": 2500,
            "term": 48,
            "payment_frequency": "biweekly",
            "payment_amount": 639.99,
            "base_payment": 639.99,
        }
    )
    # Suspicious placeholders remain when no labeled alternates exist in raw JSON.
    assert cleaned["capital_cost"] == 38715
    assert cleaned["cash_down"] == 1000


def test_clean_fixes_swapped_term_48_in_num_payments_and_rate_as_payment():
    """term=22 is infer_term(48,biweekly); 599.99 is rate 5.99 misread as payment."""
    cleaned = _clean(
        {
            "deal_type": "lease",
            "term": 22,
            "num_payments": 48,
            "payment_frequency": "biweekly",
            "rate_pct": 0,
            "rate": 5.99,
            "payment_amount": 599.99,
            "payment": 253.29,
            "base_pmt": 220.25,
            "residual_pct": 47,
            "residual_value": 0,
            "km_per_year": 0,
            "odometer_at_deal": 0,
            "make": "Volkswagen",
            "model": "Tiguan",
            "model_year": 2023,
            "vehicle": "2022 VOLKSWAGEN TIGUAN COMFORTLINE",
            "contract_date": "2023-09-08",
            "customer": {"contract_date": "09/16/2022", "delivery_date": "09/22/2022"},
            "delivery_date": "2023-09-08",
            "first_payment_date": "2023-10-08",
            "payment_date": "10/07/2022",
        }
    )
    assert cleaned["term"] == 48
    assert cleaned["num_payments"] == 104
    assert cleaned["payment_frequency"] == "biweekly"
    assert cleaned["rate_pct"] == 5.99
    assert cleaned["payment_amount"] == 253.29
    assert cleaned["base_payment"] == 220.25
    assert cleaned["model_year"] == 2022
    assert cleaned["contract_date"] == "2022-09-16"
    assert cleaned["delivery_date"] == "2022-09-22"
    assert cleaned["first_payment_date"] == "2022-10-07"
    assert cleaned["odometer_at_deal"] is None
    assert cleaned["km_per_year"] is None or cleaned["km_per_year"] == 20000


# ─── API fixtures ────────────────────────────────────────────────────────────────


class FakeLLM:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return self._responses.pop(0)


def _text_response(content: str) -> dict:
    return {
        "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": content}}
        ]
    }


def _cv2_missing():
    return patch("app.agents.deal_extractor.cv2", None), patch("app.agents.deal_extractor.np", None)


@pytest.fixture
def uploads_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "uploads_dir", str(tmp_path))
    return tmp_path


async def _seed_customer(db_session, sales_user, **kwargs) -> Customer:
    customer = Customer(
        assigned_sales_id=sales_user.id,
        full_name=kwargs.pop("full_name", "Brianna C Algee"),
        phone=kwargs.pop("phone", "(902) 555-0131"),
        email=kwargs.pop("email", "brianna@example.com"),
        **kwargs,
    )
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)
    return customer


_EXTRACTION_JSON = {
    "deal_type": "finance",
    "contract_date": "11/04/2022",
    "make": "Volkswagen",
    "model": "Tiguan",
    "model_year": 2020,
    "trim_base": "Comfortline",
    "selling_price": "36,750.00",
    "rate_pct": 0,
    "term": 72,
    "num_payments": 72,
    "payment_frequency": "Monthly",
    "payment_amount": "394.12",
    "capital_cost": "28,376.37",
    "tax_total": "3,948.22",
    "total_with_tax": "30,376.37",
    "line_items": [
        {"item_name": "Discount in lieu of PPM", "category": "discount", "amount": "(700.00)"},
        {"item_name": "Discount", "category": "discount", "amount": "(2,000.00)"},
        {"item_name": "Admin Fee", "category": "admin", "amount": "499.00"},
    ],
    "trades": [
        {"make": "Volkswagen", "model": "Jetta Sedan", "model_year": 2015,
         "trim_base": "Trendline", "vin": "3VW1K7AJ9FM339907",
         "allocation": "8,650.00", "lien_payout": "0.00"},
    ],
    "customer": {"name": "Brianna C Algee", "phone": "902-555-0131", "email": None},
    "confidence": 0.9,
}


# ─── /extract ───────────────────────────────────────────────────────────────────


async def test_extract_returns_preview_and_candidates(
    client, db_session, sales_user, sales_headers, uploads_tmp
):
    await _seed_customer(db_session, sales_user)
    fake = FakeLLM([_text_response("```json\n" + json.dumps(_EXTRACTION_JSON) + "\n```")])
    app.dependency_overrides[deals_api._llm_for_extract] = lambda: fake
    try:
        resp = await client.post(
            "/api/deals/extract",
            files={"file": ("contract.jpg", b"\xff\xd8fakejpeg", "image/jpeg")},
            headers=sales_headers,
        )
    finally:
        del app.dependency_overrides[deals_api._llm_for_extract]

    assert resp.status_code == 200, resp.text
    body = resp.json()
    extracted = body["extracted"]
    assert extracted["deal_type"] == "finance"
    assert extracted["contract_date"] == "2022-11-04"
    assert extracted["contract_end_date"] == "2028-11-04"
    assert extracted["rate_pct"] == 0  # 0% promo preserved
    assert extracted["payment_frequency"] == "monthly"
    assert len(extracted["line_items"]) == 3
    assert extracted["trades"][0]["allocation"] == 8650.0
    # phone matched the seeded customer despite different formatting
    assert body["candidates"][0]["matched_on"] == "phone"
    assert body["raw"]["contract_date"] == "11/04/2022"
    assert body["image_filename"].endswith(".jpg")
    assert (uploads_tmp / "deals" / body["image_filename"]).exists()
    # vision call used extended limits
    assert fake.calls[0]["timeout"] == 300


async def test_extract_uses_best_pseudo_scan_when_primary_is_bad(
    client, db_session, sales_user, sales_headers, uploads_tmp
):
    await _seed_customer(db_session, sales_user)
    bad = dict(_EXTRACTION_JSON)
    bad.update(
        {
            "deal_type": "lease",
            "term": 36,
            "num_payments": 36,
            "payment_frequency": "monthly",
            "payment_amount": 1211.11,
            "line_items": [],
            "rate_pct": 5.99,
        }
    )
    good = dict(_EXTRACTION_JSON)
    good.update(
        {
            "deal_type": "lease",
            "term": 48,
            "num_payments": 104,
            "payment_frequency": "biweekly",
            "payment_amount": 253.29,
            "base_payment": 220.25,
            "rate_pct": 5.99,
        }
    )
    fake = FakeLLM(
        [
            _text_response(json.dumps(bad)),
            _text_response(json.dumps(good)),
            _text_response(json.dumps(good)),  # focused lease pass
        ]
    )
    app.dependency_overrides[deals_api._llm_for_extract] = lambda: fake
    try:
        with patch(
            "app.agents.deal_extractor._build_pseudo_scans",
            return_value=[("edge_lease", b"scanpng", "image/png")],
        ):
            resp = await client.post(
                "/api/deals/extract",
                files={"file": ("contract.jpg", b"\xff\xd8fakejpeg", "image/jpeg")},
                headers=sales_headers,
            )
    finally:
        del app.dependency_overrides[deals_api._llm_for_extract]

    assert resp.status_code == 200, resp.text
    body = resp.json()
    extracted = body["extracted"]
    assert extracted["deal_type"] == "lease"
    assert extracted["term"] == 48
    assert extracted["num_payments"] == 104
    assert extracted["payment_frequency"] == "biweekly"
    assert extracted["payment_amount"] == 253.29
    assert body["raw"]["image_pass"] == "edge_lease"
    assert len(fake.calls) >= 2


async def test_extract_skips_pseudo_scan_when_opencv_unavailable(
    client, db_session, sales_user, sales_headers, uploads_tmp
):
    await _seed_customer(db_session, sales_user)
    fake = FakeLLM([_text_response(json.dumps(_EXTRACTION_JSON))])
    app.dependency_overrides[deals_api._llm_for_extract] = lambda: fake
    try:
        cv2_patch, np_patch = _cv2_missing()
        with cv2_patch, np_patch:
            resp = await client.post(
                "/api/deals/extract",
                files={"file": ("contract.jpg", b"\xff\xd8fakejpeg", "image/jpeg")},
                headers=sales_headers,
            )
    finally:
        del app.dependency_overrides[deals_api._llm_for_extract]

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["raw"]["image_pass"] == "original"
    assert len(fake.calls) == 1


async def test_extract_rejects_non_image(client, sales_headers, uploads_tmp):
    resp = await client.post(
        "/api/deals/extract",
        files={"file": ("contract.pdf", b"%PDF-", "application/pdf")},
        headers=sales_headers,
    )
    assert resp.status_code == 422


async def test_extract_unknown_profile_returns_404(client, sales_headers, uploads_tmp):
    resp = await client.post(
        "/api/deals/extract",
        data={"profile_id": "99999"},
        files={"file": ("contract.jpg", b"\xff\xd8fakejpeg", "image/jpeg")},
        headers=sales_headers,
    )
    assert resp.status_code == 404


async def test_extract_uses_selected_profile(
    client, db_session, sales_user, sales_headers, uploads_tmp, monkeypatch
):
    profile = LLMProfile(
        user_id=sales_user.id,
        name="Vision",
        base_url="https://vision.test/v1",
        api_key="vision-key",
        model="gemma-vision",
        is_active=False,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)

    fake = FakeLLM([_text_response("```json\n" + json.dumps(_EXTRACTION_JSON) + "\n```")])
    captured: list = []

    def _make_client(config):
        captured.append(config)
        return fake

    monkeypatch.setattr(deals_api, "LLMClient", _make_client)
    resp = await client.post(
        "/api/deals/extract",
        data={"profile_id": str(profile.id)},
        files={"file": ("contract.jpg", b"\xff\xd8fakejpeg", "image/jpeg")},
        headers=sales_headers,
    )
    assert resp.status_code == 200, resp.text
    assert len(captured) == 1
    assert captured[0].model == "gemma-vision"
    assert captured[0].base_url == "https://vision.test/v1"


# ─── create / confirm ───────────────────────────────────────────────────────────


def _deal_payload(customer_id=None, **deal_overrides) -> dict:
    deal = {
        "deal_type": "finance",
        "contract_date": "2022-11-04",
        "make": "Volkswagen",
        "model": "Tiguan",
        "model_year": 2020,
        "trim_base": "Comfortline",
        "selling_price": "36750.00",
        "rate_pct": "0",
        "term": 72,
        "payment_frequency": "monthly",
        "num_payments": 72,
        "payment_amount": "394.12",
        **deal_overrides,
    }
    payload = {
        "customer": (
            {"customer_id": customer_id}
            if customer_id is not None
            else {"new_customer": {"full_name": "Brianna C Algee", "phone": "902-555-0131"}}
        ),
        "deal": deal,
        "line_items": [
            {"item_name": "Discount in lieu of PPM", "category": "discount", "amount": "-700.00"},
            {"item_name": "Discount", "category": "discount", "amount": "-2000.00"},
            {"item_name": "Admin Fee", "category": "admin", "amount": "499.00"},
        ],
        "trades": [
            {"make": "Volkswagen", "model": "Jetta Sedan", "model_year": 2015,
             "trim_base": "Trendline", "allocation": "8650.00", "lien_payout": "0.00"},
        ],
        "extraction_raw": {"anything": "goes"},
        "extraction_confidence": "0.9",
    }
    return payload


async def test_create_deal_existing_customer_computes_summaries(
    client, db_session, sales_user, sales_headers
):
    customer = await _seed_customer(db_session, sales_user)
    resp = await client.post(
        "/api/deals", json=_deal_payload(customer.id), headers=sales_headers
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["customer_id"] == customer.id
    assert body["deal_type"] == "finance"
    # Decimals serialize as strings; compare by value (SQLite doesn't pad scale)
    assert Decimal(body["rate_pct"]) == 0  # 0% promo preserved, not null
    assert Decimal(body["discount"]) == 2700  # |−700 − 2000| computed server-side
    assert Decimal(body["fees_total"]) == 499
    assert Decimal(body["trade_equity"]) == 8650
    assert body["source"] == "manual"  # no image_filename supplied
    assert len(body["line_items"]) == 3
    assert len(body["trades"]) == 1
    assert body["verified_by"] == sales_user.id

    result = await db_session.execute(
        select(CustomerCar).where(CustomerCar.customer_id == customer.id)
    )
    car = result.scalar_one()
    assert car.ownership_type == "finance"
    assert car.lease_end_date == date(2028, 11, 4)  # 2022-11-04 + 72 mo


async def test_create_lease_deal_sets_customer_car_end_date(
    client, db_session, sales_user, sales_headers
):
    customer = await _seed_customer(db_session, sales_user)
    payload = _deal_payload(
        customer.id,
        deal_type="lease",
        contract_date="2022-06-12",
        term=48,
        residual_pct="47",
        residual_value="18983.30",
        buy_option_price="18983.30",
        km_per_year=20000,
    )
    resp = await client.post("/api/deals", json=payload, headers=sales_headers)
    assert resp.status_code == 201, resp.text

    result = await db_session.execute(
        select(CustomerCar).where(CustomerCar.customer_id == customer.id)
    )
    car = result.scalar_one()
    assert car.make == "Volkswagen"
    assert car.ownership_type == "lease"
    assert car.lease_end_date == date(2026, 6, 12)


async def test_create_deal_new_customer_created_and_assigned(
    client, db_session, sales_user, sales_headers
):
    resp = await client.post("/api/deals", json=_deal_payload(), headers=sales_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    result = await db_session.execute(
        select(Customer).where(Customer.id == body["customer_id"])
    )
    customer = result.scalar_one()
    assert customer.full_name == "Brianna C Algee"
    assert customer.assigned_sales_id == sales_user.id


async def test_create_deal_nulls_lease_fields_for_finance(
    client, db_session, sales_user, sales_headers
):
    customer = await _seed_customer(db_session, sales_user)
    payload = _deal_payload(customer.id, residual_pct="47", km_per_year=20000)
    resp = await client.post("/api/deals", json=payload, headers=sales_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["residual_pct"] is None
    assert resp.json()["km_per_year"] is None


async def test_create_lease_deal_keeps_lease_fields(
    client, db_session, sales_user, sales_headers
):
    customer = await _seed_customer(db_session, sales_user)
    payload = _deal_payload(
        customer.id,
        deal_type="lease",
        residual_pct="47",
        residual_value="18983.30",
        buy_option_price="18983.30",
        km_per_year=20000,
        excess_km_rate="0.12",
        security_deposit="550.00",
    )
    resp = await client.post("/api/deals", json=payload, headers=sales_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert Decimal(body["residual_pct"]) == 47
    assert body["km_per_year"] == 20000


async def test_create_deal_requires_exactly_one_customer_ref(client, sales_headers):
    payload = _deal_payload()
    payload["customer"] = {}
    resp = await client.post("/api/deals", json=payload, headers=sales_headers)
    assert resp.status_code == 422


async def test_create_deal_rejects_path_traversal_filename(
    client, db_session, sales_user, sales_headers
):
    customer = await _seed_customer(db_session, sales_user)
    payload = _deal_payload(customer.id)
    payload["image_filename"] = "../../etc/passwd"
    resp = await client.post("/api/deals", json=payload, headers=sales_headers)
    assert resp.status_code == 422


# ─── scoping ────────────────────────────────────────────────────────────────────


async def test_deals_scoped_to_customer_owner(
    client, db_session, sales_user, other_sales_user, sales_headers,
    other_sales_headers, manager_headers,
):
    customer = await _seed_customer(db_session, sales_user)
    resp = await client.post(
        "/api/deals", json=_deal_payload(customer.id), headers=sales_headers
    )
    deal_id = resp.json()["id"]

    # owner sees it
    resp = await client.get("/api/deals", headers=sales_headers)
    assert [d["id"] for d in resp.json()] == [deal_id]
    # other sales rep does not
    resp = await client.get("/api/deals", headers=other_sales_headers)
    assert resp.json() == []
    resp = await client.get(f"/api/deals/{deal_id}", headers=other_sales_headers)
    assert resp.status_code == 403
    # other rep cannot attach a deal to someone else's customer
    resp = await client.post(
        "/api/deals", json=_deal_payload(customer.id), headers=other_sales_headers
    )
    assert resp.status_code == 403
    # manager sees everything
    resp = await client.get("/api/deals", headers=manager_headers)
    assert [d["id"] for d in resp.json()] == [deal_id]


# ─── delete / cascade ───────────────────────────────────────────────────────────


async def test_delete_deal_cascades_children(
    client, db_session, sales_user, sales_headers
):
    customer = await _seed_customer(db_session, sales_user)
    resp = await client.post(
        "/api/deals", json=_deal_payload(customer.id), headers=sales_headers
    )
    deal_id = resp.json()["id"]

    resp = await client.delete(f"/api/deals/{deal_id}", headers=sales_headers)
    assert resp.status_code == 204

    assert (await db_session.execute(select(Deal))).scalars().all() == []
    assert (await db_session.execute(select(DealLineItem))).scalars().all() == []
    assert (await db_session.execute(select(DealTrade))).scalars().all() == []
