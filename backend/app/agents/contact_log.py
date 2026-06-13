import json
import re
from datetime import datetime
from typing import Any

from app.llm.client import LLMClient

_SYSTEM = """You are a contact-log parsing assistant for a car dealership CRM.
Your job is to read a raw conversation thread (email chain, SMS record, call notes, or any mix)
and extract the key details of the most recent or most significant interaction.

Rules:
- channel must be exactly one of: "call", "text", "email", "in-person"
  • If the thread was exchanged via email, use "email".
  • If it is SMS/text messages, use "text".
  • If it describes a phone call, use "call".
  • If it describes a visit to the dealership, use "in-person".
  • If ambiguous, prefer "email" for written exchanges, "call" for verbal.
- summary must be a single concise paragraph (at most 300 words) capturing:
  • the main purpose of the interaction
  • any commitments, follow-ups, or next steps mentioned
  • relevant vehicle details if discussed
  Never copy large blocks of the raw thread verbatim into the summary.
- contacted_at: extract the most recent explicit date/time mentioned in the thread as an
  ISO 8601 string (e.g. "2026-06-03T00:00:00"). If no date is mentioned, omit this field entirely.
- customer_name_hint: extract the customer's full name from the thread.
  If the name cannot be determined, use an empty string "".

Call parse_contact_log exactly once with the extracted fields."""

_PARSE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "parse_contact_log",
        "description": "Extract structured contact log fields from a raw conversation thread.",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "enum": ["call", "text", "email", "in-person"],
                    "description": "Communication channel of the interaction.",
                },
                "summary": {
                    "type": "string",
                    "description": "Concise summary of the interaction (at most 300 words).",
                },
                "customer_name_hint": {
                    "type": "string",
                    "description": "Customer's full name extracted from the thread, or empty string.",
                },
                "contacted_at": {
                    "type": "string",
                    "description": "ISO 8601 datetime of when contact occurred. Omit if not determinable.",
                },
            },
            "required": ["channel", "summary", "customer_name_hint"],
        },
    },
}

_VALID_CHANNELS = frozenset({"call", "text", "email", "in-person"})


def _validate_and_clean(args: dict[str, Any]) -> None:
    if args.get("channel") not in _VALID_CHANNELS:
        raise ValueError(f"Invalid channel from agent: {args.get('channel')!r}")

    summary = args.get("summary", "")
    if len(summary) > 2000:
        args["summary"] = summary[:1997] + "..."

    if "contacted_at" in args:
        try:
            datetime.fromisoformat(args["contacted_at"])
        except (ValueError, TypeError):
            del args["contacted_at"]


async def run_contact_log_parser(raw_text: str, llm: LLMClient) -> dict[str, Any]:
    response = await llm.chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": raw_text},
        ],
        tools=[_PARSE_TOOL],
        tool_choice="required",
    )

    tool_calls = response["choices"][0]["message"].get("tool_calls") or []
    if not tool_calls:
        # Local models may return JSON in text content instead of structured tool_calls
        content = response["choices"][0]["message"].get("content", "")
        clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        json_match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
        if not json_match:
            raise ValueError("Contact log agent did not produce a structured result.")
        args = json.loads(json_match.group())
        _validate_and_clean(args)
        return args

    args = json.loads(tool_calls[0]["function"]["arguments"])
    _validate_and_clean(args)
    return args
