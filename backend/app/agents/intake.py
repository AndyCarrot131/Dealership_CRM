import json
from typing import Any

from app.llm.client import LLMClient

_SYSTEM_PROMPT = """You are an AI assistant for a car dealership CRM.
Your job is to help sales staff add new customers and their vehicles by understanding natural language descriptions.
When the user describes a new customer, extract the information and call the create_customer_intake tool.
If information is missing or unclear, ask a clarifying question instead of guessing.
Always confirm what you extracted before the user commits."""

_INTAKE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "create_customer_intake",
        "description": "Extract and structure customer information from natural language",
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string", "description": "Customer full name"},
                "email": {"type": "string", "description": "Email address"},
                "phone": {"type": "string", "description": "Phone number"},
                "note": {"type": "string", "description": "Any additional notes about the customer"},
                "car_make": {"type": "string", "description": "Vehicle manufacturer (e.g. Toyota)"},
                "car_model": {"type": "string", "description": "Vehicle model (e.g. Camry)"},
                "car_year": {"type": "integer", "description": "Vehicle model year"},
                "car_ownership_type": {
                    "type": "string",
                    "enum": ["own", "lease", "finance"],
                    "description": "How the customer holds the vehicle: own (paid off / used), lease, or finance",
                },
            },
            "required": ["full_name"],
        },
    },
}


def _format_confirmation(fields: dict[str, Any]) -> str:
    lines = [f"**{fields['full_name']}**"]
    if fields.get("phone"):
        lines.append(f"Phone: {fields['phone']}")
    if fields.get("email"):
        lines.append(f"Email: {fields['email']}")
    if fields.get("note"):
        lines.append(f"Note: {fields['note']}")

    car_parts = [
        str(fields["car_year"]) if fields.get("car_year") else None,
        fields.get("car_make"),
        fields.get("car_model"),
    ]
    car_str = " ".join(p for p in car_parts if p)
    if car_str:
        ownership_labels = {"own": "Owned", "lease": "Lease", "finance": "Financed"}
        ownership = fields.get("car_ownership_type", "")
        label = ownership_labels.get(ownership, ownership)
        lines.append(f"Vehicle: {car_str}" + (f" ({label})" if label else ""))

    body = "\n".join(f"• {l}" if i > 0 else l for i, l in enumerate(lines))
    return f"I'll add:\n{body}\n\nConfirm?"


async def run_intake(history: list[dict[str, Any]], llm: LLMClient) -> dict[str, Any]:
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}, *history]
    response = await llm.chat(messages, tools=[_INTAKE_TOOL])

    choice = response["choices"][0]
    message = choice["message"]
    finish_reason = choice.get("finish_reason")

    if finish_reason == "tool_calls" and message.get("tool_calls"):
        tool_call = message["tool_calls"][0]
        fields: dict[str, Any] = json.loads(tool_call["function"]["arguments"])
        return {
            "intent": "create_customer",
            "fields": fields,
            "reply": _format_confirmation(fields),
        }

    content = message.get("content") or "I didn't understand that. Could you describe the customer?"
    return {"intent": "unknown", "fields": None, "reply": content}
