import json
from typing import Any

from app.llm.client import LLMClient

_UPDATE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "update_customer_fields",
        "description": "Produce a diff of fields to update on a customer and/or their car. Only include fields that should change.",
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "note": {"type": "string"},
                "car_id": {
                    "type": "integer",
                    "description": "ID of the car to update. Required if updating any car fields.",
                },
                "car_make": {"type": "string"},
                "car_model": {"type": "string"},
                "car_year": {"type": "integer"},
                "car_ownership_type": {
                    "type": "string",
                    "enum": ["own", "lease", "finance"],
                },
                "car_lease_end_date": {
                    "type": "string",
                    "description": "ISO date YYYY-MM-DD",
                },
            },
            "required": [],
        },
    },
}


def _build_system(snapshot: dict[str, Any]) -> str:
    cars_text = ""
    for car in snapshot.get("cars", []):
        parts = [
            f"id={car['id']}",
            car.get("year") and f"year={car['year']}",
            car.get("make") and f"make={car['make']}",
            car.get("model") and f"model={car['model']}",
            car.get("ownership_type") and f"ownership={car['ownership_type']}",
            car.get("lease_end_date") and f"lease_end={car['lease_end_date']}",
        ]
        cars_text += "  • " + ", ".join(p for p in parts if p) + "\n"

    return f"""You are an AI assistant for a car dealership CRM.
Your job is to help sales staff update an existing customer's record.

Current customer record:
  Name: {snapshot.get("full_name", "")}
  Phone: {snapshot.get("phone") or "(none)"}
  Email: {snapshot.get("email") or "(none)"}
  Note: {snapshot.get("note") or "(none)"}
  Cars:
{cars_text or "  (none)"}

When the user describes a change, call update_customer_fields with ONLY the fields that should change.
If updating a car, include car_id from the list above.
If information is ambiguous, ask a clarifying question before calling the tool.
Confirm what you are about to change before the tool is called."""


def _format_diff_reply(diff: dict[str, Any]) -> str:
    customer_changes = {
        k: v
        for k, v in diff.items()
        if k not in {"car_id", "car_make", "car_model", "car_year", "car_ownership_type", "car_lease_end_date"}
    }
    car_changes = {
        k: v
        for k, v in diff.items()
        if k in {"car_make", "car_model", "car_year", "car_ownership_type", "car_lease_end_date"}
    }

    lines: list[str] = ["I'll update:"]
    for field, val in customer_changes.items():
        lines.append(f"  • {field}: {val}")
    if car_changes:
        car_id = diff.get("car_id", "?")
        lines.append(f"  Car (id={car_id}):")
        for field, val in car_changes.items():
            lines.append(f"    – {field.removeprefix('car_')}: {val}")
    lines.append("\nConfirm?")
    return "\n".join(lines)


async def run_update(
    history: list[dict[str, Any]],
    customer_snapshot: dict[str, Any],
    llm: LLMClient,
) -> dict[str, Any]:
    system = _build_system(customer_snapshot)
    messages = [{"role": "system", "content": system}, *history]
    response = await llm.chat(messages, tools=[_UPDATE_TOOL])

    choice = response["choices"][0]
    message = choice["message"]
    finish_reason = choice.get("finish_reason")

    if finish_reason == "tool_calls" and message.get("tool_calls"):
        tool_call = message["tool_calls"][0]
        diff: dict[str, Any] = json.loads(tool_call["function"]["arguments"])
        return {
            "intent": "update_customer",
            "diff": diff,
            "reply": _format_diff_reply(diff),
        }

    content = message.get("content") or "I didn't understand. Could you describe what changed?"
    return {"intent": "unknown", "diff": None, "reply": content}
