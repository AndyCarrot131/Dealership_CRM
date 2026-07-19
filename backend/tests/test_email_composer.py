import json

from app.agents.email_composer import compose_email


class RecordingLLM:
    def __init__(self):
        self.kwargs = None

    async def chat(self, messages, **kwargs):
        self.kwargs = kwargs
        self.messages = messages
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"subject": "Checking in", "body": "Hi Alex,\n\nHow are you?"}
                        )
                    }
                }
            ]
        }


async def test_compose_email_requests_bounded_structured_low_reasoning_output():
    llm = RecordingLLM()

    await compose_email(
        customer={"full_name": "Alex Smith", "cars": [], "interactions": []},
        inventory_matches=[],
        style_md="",
        llm=llm,
        email_type="test_drive_followup",
    )

    assert llm.kwargs == {
        "max_tokens": 2000,
        "temperature": 0.2,
        "reasoning_effort": "low",
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }


async def test_compose_email_redacts_customer_pii_before_llm_call_and_restores_response():
    class EchoPlaceholderLLM:
        async def chat(self, messages, **kwargs):
            prompt = messages[1]["content"]
            assert "Alex Smith" not in prompt
            assert "902-555-0100" not in prompt
            assert "10 Main Street" not in prompt
            name_token = next(part.split("]]", 1)[0] + "]]" for part in prompt.split() if part.startswith("[[PII_FULL_NAME_"))
            phone_token = next(part for part in prompt.split() if part.startswith("[[PII_PHONE_"))
            return {
                "choices": [{"message": {"content": json.dumps({
                    "subject": f"Hello {name_token}",
                    "body": f"Hi {name_token}, call {phone_token}",
                })}}]
            }

    result = await compose_email(
        customer={
            "full_name": "Alex Smith",
            "phone": "902-555-0100",
            "address": "10 Main Street",
            "cars": [],
            "interactions": [],
        },
        inventory_matches=[],
        style_md="",
        llm=EchoPlaceholderLLM(),
        email_type="test_drive_followup",
    )

    assert result == {
        "subject": "Hello Alex Smith",
        "body": "Hi Alex Smith, call 902-555-0100",
    }
