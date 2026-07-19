import json

from app.agents.text_composer import compose_text


async def test_compose_text_redacts_customer_pii_and_restores_response():
    class EchoPlaceholderLLM:
        async def chat(self, messages, **kwargs):
            prompt = messages[1]["content"]
            assert "Alex Smith" not in prompt
            assert "902-555-0100" not in prompt
            name_token = next(part.split("]]", 1)[0] + "]]" for part in prompt.split() if part.startswith("[[PII_FULL_NAME_"))
            return {"choices": [{"message": {"content": json.dumps({"body": f"Hi {name_token}!"})}}]}

    result = await compose_text(
        customer={"full_name": "Alex Smith", "phone": "902-555-0100", "cars": []},
        inventory_matches=[],
        style_md="",
        llm=EchoPlaceholderLLM(),
        email_type="test_drive_followup",
    )

    assert result == {"subject": "", "body": "Hi Alex Smith!"}
