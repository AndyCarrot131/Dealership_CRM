import json

from app.agents.email_composer import compose_email


class RecordingLLM:
    def __init__(self):
        self.kwargs = None

    async def chat(self, messages, **kwargs):
        self.kwargs = kwargs
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
