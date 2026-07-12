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


async def test_compose_email_caps_output_and_disables_thinking():
    llm = RecordingLLM()

    await compose_email(
        customer={"full_name": "Alex Smith", "cars": [], "interactions": []},
        inventory_matches=[],
        style_md="",
        llm=llm,
        email_type="test_drive_followup",
    )

    assert llm.kwargs == {
        "max_tokens": 1000,
        "chat_template_kwargs": {"enable_thinking": False},
    }
