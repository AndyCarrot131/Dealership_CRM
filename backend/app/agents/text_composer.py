import json
import re
from typing import Any

from app.llm.client import LLMClient

_SYSTEM = """You are an AI text-message writing assistant for a car dealership sales representative.
Your task is to compose a short, personalised SMS text message to a specific customer.

You will receive:
1. Outreach purpose (the reason for reaching out)
2. Customer profile (name, note, vehicles they own/lease)
3. Matching inventory vehicles that may be relevant
4. The sales representative's writing style guide (in Markdown)

Rules:
- Keep the message to 2–3 sentences (50–100 words maximum)
- Match the representative's voice from the style guide; if unspecified, write in a warm, casual tone
- Make it feel personal — reference the customer's specific situation
- No formal subject line, no lengthy sign-off; end with the rep's first name or a brief sign-off only
- Respond ONLY with a JSON object in the exact format:
  {"body": "..."}"""

_TYPE_CONTEXT: dict[str, str] = {
    "test_drive_followup": (
        "The customer recently test-drove a vehicle. "
        "Send a brief, friendly follow-up thanking them and keeping the conversation going."
    ),
    "lease_finance_ending": (
        "The customer's lease or financing is ending soon. "
        "Send a short message about upgrade options and next steps."
    ),
}


def _build_user_message(
    customer: dict[str, Any],
    inventory_matches: list[dict[str, Any]],
    style_md: str,
    email_type: str = "lease_finance_ending",
    custom_template: str | None = None,
) -> str:
    car_lines = []
    for car in customer.get("cars", []):
        parts = [
            car.get("year") and str(car["year"]),
            car.get("make"),
            car.get("model"),
            car.get("ownership_type") and f"({car['ownership_type']})",
            car.get("lease_end_date") and f"lease ends {car['lease_end_date']}",
        ]
        car_lines.append(" ".join(p for p in parts if p))

    inventory_lines = []
    for item in inventory_matches[:2]:
        parts = [
            item.get("year") and str(item["year"]),
            item.get("make"),
            item.get("model"),
            item.get("trim"),
            item.get("price") and f"${item['price']:,.0f}",
        ]
        inventory_lines.append(" ".join(p for p in parts if p))

    if email_type == "custom" and custom_template:
        purpose = f"Use the following dealer-provided topic as the theme:\n{custom_template}"
    else:
        purpose = _TYPE_CONTEXT.get(email_type, _TYPE_CONTEXT["lease_finance_ending"])

    sections = [
        f"Outreach purpose: {purpose}",
        f"Customer: {customer['full_name']}",
        f"Note: {customer.get('note') or '(none)'}",
        "Customer vehicles:\n" + ("\n".join(f"  • {l}" for l in car_lines) or "  (none)"),
        "Relevant inventory:\n" + ("\n".join(f"  • {l}" for l in inventory_lines) or "  (none)"),
        "Style guide:\n" + (style_md or "(no style guide — write in a warm, casual tone)"),
    ]
    return "\n\n".join(sections)


async def compose_text(
    customer: dict[str, Any],
    inventory_matches: list[dict[str, Any]],
    style_md: str,
    llm: LLMClient,
    email_type: str = "lease_finance_ending",
    custom_template: str | None = None,
) -> dict[str, str]:
    user_msg = _build_user_message(customer, inventory_matches, style_md, email_type, custom_template)
    response = await llm.chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_msg},
        ]
    )
    content = response["choices"][0]["message"].get("content", "")
    clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    json_match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
    try:
        parsed = json.loads(json_match.group() if json_match else clean)
        body = str(parsed.get("body", "")).strip()
    except (json.JSONDecodeError, AttributeError):
        body = clean

    if not body:
        body = f"Hi {customer['full_name']}, just checking in — let me know if you have any questions!"
    return {"subject": "", "body": body}
