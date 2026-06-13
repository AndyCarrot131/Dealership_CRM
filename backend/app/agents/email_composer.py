import json
import re
from typing import Any

from app.llm.client import LLMClient

_SYSTEM = """You are an AI email-writing assistant for a car dealership sales representative.
Your task is to compose a personalised outreach email to a specific customer.

You will receive:
1. Email purpose (the reason for reaching out)
2. Customer profile (name, note, vehicles they own/lease)
3. Matching inventory vehicles that may be relevant to this customer
4. The sales representative's writing style guide (in Markdown)
5. Customer's full contact log (channel, date, summary of each prior interaction)

Rules:
- Match the representative's voice and style exactly as described in the style guide
- Make the email feel personal and relevant to this specific customer's situation
- Use the contact log to avoid repeating topics already covered, acknowledge the relationship naturally, and pick up where the last conversation left off
- Reference their vehicle(s) naturally (e.g., lease end dates, age, type)
- Mention 1-2 inventory options at most; do not list every car
- Follow the word count and paragraph count specified in the style guide; if unspecified, target 180–260 words
- Always include a warm closing paragraph thanking the customer, a soft CTA (reply or call), and a professional sign-off with name and title
- Do NOT include a subject line in the body
- Respond ONLY with a JSON object in the exact format:
  {"subject": "...", "body": "..."}"""

_TYPE_CONTEXT: dict[str, str] = {
    "test_drive_followup": (
        "The customer recently test-drove a vehicle. "
        "Write a warm follow-up email thanking them for the test drive and keeping them engaged."
    ),
    "lease_finance_ending": (
        "The customer's lease or financing is ending soon. "
        "Write an email about upgrade options and next steps."
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
    for item in inventory_matches[:3]:
        parts = [
            item.get("year") and str(item["year"]),
            item.get("make"),
            item.get("model"),
            item.get("trim"),
            item.get("price") and f"${item['price']:,.0f}",
        ]
        inventory_lines.append(" ".join(p for p in parts if p))

    if email_type == "custom" and custom_template:
        purpose = f"Use the following dealer-provided topic as the theme of this email:\n{custom_template}"
    else:
        purpose = _TYPE_CONTEXT.get(email_type, _TYPE_CONTEXT["lease_finance_ending"])

    contact_lines = []
    for entry in customer.get("interactions", []):
        contact_lines.append(
            f"  • [{entry.get('date', '?')}] {entry.get('channel', '?')}: {entry.get('summary', '')}"
        )

    sections = [
        f"Email purpose: {purpose}",
        f"Customer: {customer['full_name']}",
        f"Note: {customer.get('note') or '(none)'}",
        "Customer vehicles:\n" + ("\n".join(f"  • {l}" for l in car_lines) or "  (none)"),
        "Relevant inventory:\n" + ("\n".join(f"  • {l}" for l in inventory_lines) or "  (none)"),
        "Contact history (newest first):\n" + ("\n".join(contact_lines) or "  (no prior contact logged)"),
        "Style guide:\n" + (style_md or "(no style guide — write professionally)"),
    ]
    return "\n\n".join(sections)


async def compose_email(
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
    # Strip <think>...</think> reasoning blocks emitted by some models
    clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    # Extract the first {...} JSON object from the cleaned text
    json_match = re.search(r"\{.*\}", clean, flags=re.DOTALL)
    try:
        parsed = json.loads(json_match.group() if json_match else clean)
        subject = str(parsed.get("subject", "")).strip()
        body = str(parsed.get("body", "")).strip()
    except (json.JSONDecodeError, AttributeError):
        lines = clean.split("\n", 1)
        subject = lines[0].removeprefix("Subject:").strip()
        body = lines[1].strip() if len(lines) > 1 else clean

    if not subject:
        subject = f"Checking in — {customer['full_name']}"
    return {"subject": subject, "body": body}
