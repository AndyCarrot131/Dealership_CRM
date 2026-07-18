import json
from pathlib import Path

from app.agents.contact_log import run_contact_log_parser
from app.agents.email_composer import compose_email
from app.agents.style_summarizer import run_style_summarizer


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gemini_contract_responses.json"


class FixtureLLM:
    def __init__(self, *responses):
        self.responses = list(responses)

    async def chat(self, messages, **kwargs):
        return self.responses.pop(0)


def _responses():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


async def test_sanitized_gemini_contact_contract_is_supported():
    llm = FixtureLLM(_responses()["contact_log"])
    result = await run_contact_log_parser("Fixture call notes", llm)
    assert result["channel"] == "call"
    assert result["customer_name_hint"] == "Fixture Customer"
    assert "Tiguan" in result["summary"]


async def test_sanitized_gemini_style_and_email_contracts_are_supported():
    responses = _responses()
    style_llm = FixtureLLM(responses["style_summary"])
    style = await run_style_summarizer(
        [("lease maturity", "Hi Alex, your Tiguan lease is ending soon.")],
        "email",
        style_llm,
    )
    assert "Warm, professional" in style

    email_llm = FixtureLLM(responses["email_draft"])
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
        llm=email_llm,
        email_type="test_drive_followup",
    )
    assert "Fixture" in draft["subject"]
    assert "Tiguan" in draft["subject"]
    assert "2026 Volkswagen Tiguan Highline R-Line" in draft["body"]
